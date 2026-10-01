"""Instrumentação M2M: contadores de chamadas de máquina externas por canal.

Cada requisição elegível emite um log estruturado `AETHERX_METRIC` (fonte
durável no Railway) e atualiza contadores em memória, expostos em
`/internal/metrics` (protegido pelo proxy secret). Objetivo: medir o KPI
"External Machine Calls" por ecossistema — MCP, REST, discovery e SEO de bots.
"""

import collections
import hashlib
import json
import logging
import os
import threading
import time

logger = logging.getLogger("aetherx.metrics")

# Versão da aplicação exposta no /internal/metrics (diagnóstico de rollout).
APP_VERSION = os.getenv("AETHERX_APP_VERSION", "1.3.3")

# Rotas que não interessam ao KPI (liveness, docs, assets).
_SKIP_PREFIXES = ("/health", "/docs", "/redoc", "/static", "/tzdata/")

# Paths de descoberta por máquina (agent-friendly), contados à parte.
_DISCOVERY_PATHS = (
    "/openapi.json",
    "/openapi.rapidapi.json",
    "/llms.txt",
    "/.well-known/ai-plugin.json",
    "/sitemap.xml",
    "/robots.txt",
)

# Bot/crawler/liveness: NÃO contam como usuário máquina externo para o funil
# M2M (ex.: SentinelOracle, mcpbeat, rokmcp, Googlebot). São medidos à parte em "bot".
_BOT_TOKENS = (
    "sentineloracle", "mcpbeat", "rokmcp", "googlebot", "bingbot", "slurp",
    "duckduckbot", "baiduspider", "yandex", "lighthouse", "gtmetrix",
    "uptimerobot", "pingdom", "statuscake", "monitoring", "pingbot",
    "facebookexternalhit", "twitterbot", "linkedinbot", "glimind",
)

# Firma de user-agent indica máquina (bot/agente/cliente HTTP), não humano.
_MACHINE_TOKENS = (
    "bot", "spider", "crawl", "curl", "httpx", "requests", "aiohttp",
    "go-http-client", "node-fetch", "axios", "okhttp", "wget", "java",
    "claude", "gpt", "openai", "google-cloud", "browsermob",
)

# Token do próprio projeto: ignora chamadas de nossos próprios health-check.
_SELF_TOKENS = ("belegante-aetherx",)

_lock = threading.RLock()
_counts = {}      # {channel: int}
_uniq = {}        # {channel: set[str]}   hash do IP do cliente
_machines = {}    # {channel: collections.Counter[str]}  chamadas por máquina
_paths = {}       # {path: int}
_t0 = time.time()

# ---- Persistência: contadores sobrevivem a restarts/deploys ----
# O Railway é efêmero (sem volume), então persistimos o estado em arquivo a
# cada ~30s e no shutdown, recarregando no boot. O dashboard local (Mac)
# acumula histórico durável separadamente.
_STATE_PATH = os.environ.get("AETHERX_METRICS_STATE", "data/metrics_state.json")
_STATE_INTERVAL = int(os.environ.get("AETHERX_METRICS_PERSIST_S", "30"))
_persist_thread = None
_persist_stop = threading.Event()

# ---- Control Tower: uso de produto (tool, porto, status, latência) ----
_tools = {}            # {tool_name: int}
_ports = {}            # {port_id: int}
_recent_events = collections.deque(maxlen=100)  # [{ts, kind, detail}]
_mcp_errors = 0        # total de erros em invocações de tool
_mcp_total = 0         # total de invocações de tool
_errors_total = 0      # erros HTTP (5xx) observados

_EVENT_KINDS = ("mcp_call", "tool_call", "new_machine", "repeat_machine", "port_query", "error")

# ---- Erros de tool MCP atribuíveis (mitigação auditoria 2026-09-21) ----
# Antes, ok=False apenas incrementava _mcp_errors — impossível saber qual tool/
# porto/erro falhou. Este deque (persistido) guarda as últimas causas.
_tool_errors = collections.deque(maxlen=50)  # [{ts, tool, port, error_type, error}]

# ---- Monetização: assinantes pagos vistos via gateway RapidAPI ----
_paid_plans = {}      # {plan_name: int}  chamadas por tier pago (PRO/ULTRA/MEGA/CUSTOM)
_paid_users = set()   # set[str]          X-RapidAPI-User distintos em plano pago

PAID_PLANS = ("PRO", "ULTRA", "MEGA", "CUSTOM")

# ---- Gate de acesso MCP (diagnóstico do funil de conversão) ----
# Quantificam onde o funil "vaza" e alimentam a Control Tower:
#   decision_denied  → máquinas anônimas que tentaram Decision Tools sem credencial
#   quota_exceeded   → máquinas anônimas que estouraram a quota diária de observação
#   trial_keys_issued→ trios self-service emitidos (chamadas autênticas de interesse)
_decision_denials = 0
_quota_denials = 0
_trial_keys_issued = 0

# ---- Consumidores reais: máquinas que EXECUTARAM pelo menos uma tool ----
# Distingue "consumo real do Oracle" de "handshake/liveness de crawlers".
# `_mcp_consumers` registra ip_hash de máquinas que invocaram tools/call.
_mcp_consumers = {}    # {ip_hash: int}  tools executadas por máquina
_mcp_consumer_ips = set()  # set[str]

# ---- Funil M2M por máquina anônima ----
# Cada máquina (ip_hash) tem os estágios do funil comportamental que atingiu:
#   discovery -> mcp_connect -> tool_call -> repeat_transport -> repeat_tool -> paid
# Agregado no snapshot como funnel; a Control Tower mostra máquinas individuais.
_MACHINE_STAGES = {}    # {ip_hash: set[str]}  estágios atingidos
_MACHINE_FIRST = {}     # {ip_hash: int}  ts do primeiro contato
_MACHINE_LAST = {}      # {ip_hash: int}  ts do último contato
_MACHINE_CALLS = {}     # {ip_hash: int}  total de chamadas (qualquer canal)
_MACHINE_TOOL_TS = {}   # {ip_hash: list[int]}  timestamps de tools executadas
_MACHINE_TOOL_NAMES = {} # {ip_hash: Counter[tool_name]} counts of tools called
_MACHINE_TOOL_PORTS = {}  # {ip_hash: Counter[port]}  portos consultados via tool
_MACHINE_INTENT = {}    # {ip_hash: Counter[intent]}  famílias de intenção por tool_call

# ---- Classificação por role (o que a máquina É, não só o que fez) ----
# Separa o tráfego mascarado: automated (bot/crawler/liveness) vs máquina
# de descoberta MCP vs consumidor real de produto (executou tool).
_MACHINE_ROLE = {}      # {ip_hash: str}  'automated' | 'discovery' | 'mcp_client' | 'consumer' | 'api_client' | 'seo'
_MACHINE_UA = {}        # {ip_hash: str}  user-agent truncado (diagnóstico)
_last_tool_call: dict | None = None  # último tool_call: {ts, machine, tool, port, intent, ok}

# Baseline do processo atual (para separar CURRENT WINDOW de LIFETIME).
_window_base = {}       # {'mcp_total': int, 'requests': int, 'tools': {tool:int}, 't0': float}

# Estágios do funil. Ordem: infraestrutura (descoberta/transporte) depois produto.
FUNNEL_STAGES = (
    "discovery", "mcp_connect", "tool_call", "repeat_transport", "repeat_tool", "paid",
)

# Janela (segundos) entre tool calls para considerar "retorno de produto".
# Se uma máquina executa tools com intervalo >= TOOL_REPEAT_WINDOW, é retenção
# de produto (voltou para consumir de novo), não transporte.
TOOL_REPEAT_WINDOW = int(os.environ.get("AETHERX_TOOL_REPEAT_WINDOW_S", "300"))


def _mark_stage(ip_hash: str | None, stage: str) -> None:
    if not ip_hash or stage not in FUNNEL_STAGES:
        return
    now = int(time.time())
    with _lock:
        st = _MACHINE_STAGES.setdefault(ip_hash, set())
        st.add(stage)
        _MACHINE_FIRST.setdefault(ip_hash, now)
        _MACHINE_LAST[ip_hash] = now
        _MACHINE_CALLS[ip_hash] = _MACHINE_CALLS.get(ip_hash, 0) + 1


def _record_tool_ts(ip_hash: str, port_id: str | None) -> None:
    """Registra timestamp de tool executada e detecta repeat_tool (retenção de produto).

    repeat_tool: a máquina executou tools em >=2 janelas distintas (intervalo
    >= TOOL_REPEAT_WINDOW). Distingue 'voltou para consumir o sinal' de
    'voltou ao transporte' (repeat_transport).
    """
    now = int(time.time())
    with _lock:
        ts_list = _MACHINE_TOOL_TS.setdefault(ip_hash, [])
        ts_list.append(now)
        ts_list[:] = ts_list[-50:]
        if port_id:
            _MACHINE_TOOL_PORTS.setdefault(ip_hash, collections.Counter())[port_id] += 1
        # repeat_tool: existe tool anterior em janela distinta
        if len(ts_list) >= 2 and (now - ts_list[0]) >= TOOL_REPEAT_WINDOW:
            _MACHINE_STAGES.setdefault(ip_hash, set()).add("repeat_tool")


def _classify_stage(path: str, channel: str) -> str | None:
    """Mapeia uma requisição para o estágio do funil que ela representa."""
    if path in _DISCOVERY_PATHS or path.startswith("/port-congestion-") or path == "/":
        return "discovery"
    if channel == "mcp":
        return "mcp_connect"
    if channel == "rest":
        return None  # REST usa o estágio 'paid' via subscription; consumo via tool
    return None


def _classify_machine_role(ip_hash: str, channel: str, ua: str) -> None:
    """Classifica o que uma máquina É (role), não só o canal da requisição.

    - automated: bot/crawler/liveness (health checks, diretórios MCP scanners)
    - discovery: acessou paths de descoberta (llms.txt, openapi, sitemap)
    - mcp_client: conectou ao endpoint MCP
    - api_client: usou REST
    - seo: crawler de busca (Googlebot etc.) — medido à parte
    - consumer: executou pelo menos uma tool (upgraded em record_tool_call)
    A role só sobe de 'automated' para 'consumer' — nunca desce.
    """
    with _lock:
        cur = _MACHINE_ROLE.get(ip_hash)
        ua_l = ua.lower()
        if cur == "consumer":
            return
        if any(t in ua_l for t in _BOT_TOKENS):
            role = "automated"
        elif channel == "bot":
            role = "automated"
        elif channel == "seo":
            role = "seo"
        elif channel == "discovery":
            role = "discovery"
        elif channel == "mcp":
            role = "mcp_client"
        elif channel == "rest":
            role = "api_client"
        else:
            role = "automated"
        # máquina já classificada com role mais forte não regride
        order = {"automated": 0, "seo": 1, "discovery": 2, "api_client": 3, "mcp_client": 4, "consumer": 5}
        if cur is None or order.get(role, 0) > order.get(cur, 0):
            _MACHINE_ROLE[ip_hash] = role
        if ua and ip_hash not in _MACHINE_UA:
            _MACHINE_UA[ip_hash] = ua[:60]

# Contextvar: identidade da máquina na requisição HTTP atual, lida pelo
# _run_tool para correlacionar tool -> máquina.
from contextvars import ContextVar
current_machine_id: ContextVar[str | None] = ContextVar("current_machine_id", default=None)


def set_current_machine(ip_hash: str | None) -> None:
    if ip_hash:
        current_machine_id.set(ip_hash)


def get_current_machine() -> str | None:
    return current_machine_id.get()


def record_rapidapi_call(plan: str | None, user: str | None) -> None:
    """Registra uma chamada que veio pelo gateway RapidAPI (REST).

    Detecção de monetização: quando X-RapidAPI-Subscription é um plano pago,
    registra o tier e o usuário. Requisições BASIC (grátis) ou diretas (sem
    headers) não contam como pagas.
    """
    if not plan:
        return
    plan = plan.upper()
    if plan not in PAID_PLANS:
        return
    with _lock:
        _paid_plans[plan] = _paid_plans.get(plan, 0) + 1
        if user:
            _paid_users.add(user)
        _recent_events.appendleft({
            "ts": int(time.time()),
            "kind": "paid_call",
            "detail": f"{plan} · {user or '?'}",
        })
    mid = get_current_machine()
    if mid:
        _mark_stage(mid, "paid")


def record_tool_call(tool: str, port_id: str | None = None, ok: bool = True, latency_ms: int | None = None, intent: str | None = None, error: BaseException | None = None, client_id: str | None = None) -> None:
    """Registra uma invocação de tool MCP (ou de produto) para a Control Tower.

    Quando `ok=False`, registra a CAUSA (tool + porto + tipo de erro) em log WARN
    e mantém as últimas 50 falhas em `_tool_errors` (persistido e exposto no
    snapshot), para que um número como `mcp_errors` seja auditável.
    """
    global _mcp_total, _mcp_errors, _last_tool_call
    mid = get_current_machine()
    if mid:
        _mark_stage(mid, "tool_call")
        _record_tool_ts(mid, port_id)
        _MACHINE_TOOL_NAMES.setdefault(mid, collections.Counter())[tool] += 1
        if _MACHINE_TOOL_NAMES[mid][tool] >= 2:
            _mark_stage(mid, "repeat_tool")
        if intent:
            _MACHINE_INTENT.setdefault(mid, collections.Counter())[intent] += 1
    with _lock:
        _mcp_total += 1
        _tools[tool] = _tools.get(tool, 0) + 1
        if mid:
            _mcp_consumers[mid] = _mcp_consumers.get(mid, 0) + 1
            _mcp_consumer_ips.add(mid)
            _MACHINE_ROLE[mid] = "consumer"
        if port_id:
            _ports[port_id] = _ports.get(port_id, 0) + 1
            _recent_events.appendleft({
                "ts": int(time.time()),
                "kind": "port_query",
                "detail": port_id,
            })
        _last_tool_call = {
            "ts": int(time.time()),
            "machine": mid[:8] if mid else None,
            "tool": tool,
            "port": port_id,
            "intent": intent,
            "ok": ok,
        }
        if not ok:
            _mcp_errors += 1
            err_type = type(error).__name__ if error else "unknown"
            err_msg = str(error) if error else "no error detail captured"
            _tool_errors.appendleft({
                "ts": int(time.time()),
                "tool": tool,
                "port": port_id,
                "error_type": err_type,
                "error": err_msg[:300],
                "client_id": (client_id or "")[:16],
            })
            logger.warning(
                "AETHERX_MCP_TOOL_ERROR tool=%s port=%s machine=%s type=%s err=%r",
                tool, port_id, (mid[:8] if mid else None), err_type, err_msg,
            )
        _recent_events.appendleft({
            "ts": int(time.time()),
            "kind": "tool_error" if not ok else "tool_call",
            "detail": tool,
            "ok": ok,
            "latency_ms": latency_ms,
            "intent": intent,
            "error": type(error).__name__ if (not ok and error) else None,
        })


def record_error() -> None:
    """Registra um erro HTTP 5xx (para a taxa de erro geral)."""
    global _errors_total
    with _lock:
        _errors_total += 1


def record_gate_event(kind: str) -> None:
    """Registra eventos do gate de acesso MCP (diagnóstico do funil).

    kind ∈ {"decision_denied", "quota_denied", "trial_key_issued"}.
    """
    global _decision_denials, _quota_denials, _trial_keys_issued
    if kind not in ("decision_denied", "quota_denied", "trial_key_issued"):
        return
    with _lock:
        if kind == "decision_denied":
            _decision_denials += 1
        elif kind == "quota_denied":
            _quota_denials += 1
        else:
            _trial_keys_issued += 1
        _recent_events.appendleft({"ts": int(time.time()), "kind": "gate", "detail": kind})


def record_machine_event(kind: str, detail: str) -> None:
    """Registra um evento de máquina (novo/retorno) na linha do tempo."""
    if kind not in ("new_machine", "repeat_machine"):
        return
    with _lock:
        _recent_events.appendleft({"ts": int(time.time()), "kind": kind, "detail": detail})


def _bucket(ip: str) -> str:
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]


def _classify(path: str, ua: str) -> str | None:
    """Retorna o canal da chamada, ou None se não for máquina relevante."""
    path_l = path.lower()
    ua_l = ua.lower()
    if any(t in ua_l for t in _SELF_TOKENS):
        return None
    if path_l.startswith(_SKIP_PREFIXES):
        return None
    if any(t in ua_l for t in _BOT_TOKENS):
        return "bot"
    if path_l.startswith("/mcp"):
        return "mcp"
    if path_l.startswith("/v1/"):
        return "rest"
    if path_l in _DISCOVERY_PATHS:
        return "discovery"
    if any(t in ua_l for t in _MACHINE_TOKENS):
        return "seo"
    return None


def _client_ip(headers: dict, scope) -> str:
    xff = headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


class MetricsMiddleware:
    """Middleware ASGI: registra a chamada antes de passar para o app.

    Captura o status code de resposta para contabilizar erros 5xx na Control
    Tower (error rate), além dos contadores de máquina por canal.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            status_holder = {}
            token = None
            # Identifica a máquina desta requisição para correlacionar tools
            # executadas com o consumidor real (MCP consumers).
            try:
                headers = {
                    k.decode("latin-1").lower(): v.decode("latin-1")
                    for k, v in scope.get("headers", [])
                }
                mid = _bucket(_client_ip(headers, scope))
                token = current_machine_id.set(mid)
            except Exception:
                pass

            async def send_wrapper(message):
                if message.get("type") == "http.response.start":
                    status_holder["status"] = message.get("status")
                await send(message)

            record_http(scope, status_holder=status_holder)
            try:
                await self.app(scope, receive, send_wrapper)
            finally:
                if token is not None:
                    try:
                        current_machine_id.reset(token)
                    except Exception:
                        pass
            status = status_holder.get("status")
            if status and status >= 500:
                record_error()
        else:
            await self.app(scope, receive, send)


def record_http(scope, status_holder: dict | None = None) -> None:
    path = scope.get("path", "/")
    headers = {
        k.decode("latin-1").lower(): v.decode("latin-1")
        for k, v in scope.get("headers", [])
    }
    ua = headers.get("user-agent", "")
    channel = _classify(path, ua)
    if channel == "rest":
        record_rapidapi_call(
            headers.get("x-rapidapi-subscription"),
            headers.get("x-rapidapi-user"),
        )
    if not channel:
        return
    key = _bucket(_client_ip(headers, scope))
    _classify_machine_role(key, channel, ua)
    stage = _classify_stage(path, channel)
    if stage:
        _mark_stage(key, stage)
    with _lock:
        _counts[channel] = _counts.get(channel, 0) + 1
        _uniq.setdefault(channel, set()).add(key)
        c = _machines.setdefault(channel, collections.Counter())
        is_new = key not in c
        c[key] += 1
        _paths[path] = _paths.get(path, 0) + 1
        if is_new:
            _recent_events.appendleft({"ts": int(time.time()), "kind": "new_machine", "detail": channel})
        elif c[key] >= 2:
            _recent_events.appendleft({"ts": int(time.time()), "kind": "repeat_machine", "detail": channel})
            _mark_stage(key, "repeat_transport")
    logger.info(
        "AETHERX_METRIC %s",
        json.dumps(
            {
                "channel": channel,
                "path": path,
                "ua": ua[:96],
                "ip_hash": key,
                "ts": int(time.time()),
            },
            ensure_ascii=False,
        ),
    )


def metrics_snapshot() -> dict:
    with _lock:
        uniq = {k: len(v) for k, v in _uniq.items()}
        repeat = {k: sum(1 for c in cnt.values() if c >= 2) for k, cnt in _machines.items()}
        second_call_rate = {
            k: (repeat[k] / uniq[k] if uniq.get(k) else 0.0)
            for k in repeat
        }
        total_req = sum(_counts.values())
        err_rate = (_errors_total / total_req) if total_req else 0.0
        return {
            "uptime_seconds": int(time.time() - _t0),
            "app_version": APP_VERSION,
            "total": dict(_counts),
            "bot_calls": _counts.get("bot", 0),
            "unique_machines": uniq,
            "repeat_machines": repeat,
            "second_call_rate": second_call_rate,
            "top_paths": sorted(_paths.items(), key=lambda x: -x[1])[:20],
            # Control Tower
            "requests_total": total_req,
            "mcp_calls": _mcp_total,
            "mcp_errors": _mcp_errors,
            "errors_total": _errors_total,
            "error_rate": round(err_rate, 4),
            "top_tools": sorted(_tools.items(), key=lambda x: -x[1])[:20],
            "top_ports": sorted(_ports.items(), key=lambda x: -x[1])[:20],
            "recent_events": list(_recent_events)[:50],
            "tool_errors": list(_tool_errors)[:20],
            # Monetização
            "paid_plans": dict(_paid_plans),
            "paid_users": sorted(_paid_users),
            "paid_user_count": len(_paid_users),
            # Gate de acesso MCP: onde o funil vaza + trial keys emitidos
            "gates": {
                "decision_denied": _decision_denials,
                "quota_exceeded": _quota_denials,
                "trial_keys_issued": _trial_keys_issued,
            },
            # Consumo real: máquinas que executaram tools (não liveness)
            "mcp_consumer_count": len(_mcp_consumer_ips),
            "mcp_consumers": {
                "unique": len(_mcp_consumer_ips),
                "calls_by_machine": dict(sorted(_mcp_consumers.items(), key=lambda x: -x[1])[:10]),
            },
            # Funil M2M por máquina anônima
            "funnel": {
                stage: sum(1 for st in _MACHINE_STAGES.values() if stage in st)
                for stage in FUNNEL_STAGES
            },
            "machines": [
                {
                    "id": mid[:8],
                    "first": _MACHINE_FIRST.get(mid),
                    "last": _MACHINE_LAST.get(mid),
                    "calls": _MACHINE_CALLS.get(mid, 0),
                    "stages": sorted(_MACHINE_STAGES.get(mid, set())),
                    "tools": _MACHINE_TOOL_TS.get(mid, []),
                    "ports": dict(_MACHINE_TOOL_PORTS.get(mid, {})),
                    "intent": dict(_MACHINE_INTENT.get(mid, {})),
                }
                for mid in sorted(_MACHINE_STAGES.keys(),
                                 key=lambda m: -_MACHINE_CALLS.get(m, 0))[:12]
            ],
            "intent_by_family": {
                family: sum(1 for c in _MACHINE_INTENT.values() if c.get(family))
                for family in ("congestion", "queue", "delay", "economic", "decision")
            },
            # Classificação: o que as máquinas SÃO (não só o que fizeram)
            "roles": {
                role: sum(1 for r in _MACHINE_ROLE.values() if r == role)
                for role in ("automated", "seo", "discovery", "api_client", "mcp_client", "consumer")
            },
            "last_tool_call": _last_tool_call,
            # CURRENT PROCESS WINDOW vs LIFETIME (para não confundir reset com ausência)
            "window": {
                "mcp_calls": _mcp_total - _window_base.get("mcp_total", 0),
                "requests": total_req - _window_base.get("requests", 0),
            },
            "lifetime": {
                "mcp_calls": _mcp_total,
                "requests": total_req,
            },
            # Matriz de qualidade por porto (derivada do DuckDB real a cada snapshot).
            "data_quality": _quality_matrix_snapshot(),
        }

def _quality_matrix_snapshot() -> list[dict]:
    """Deriva a matriz de qualidade dos portos a partir do DuckDB real."""
    try:
        import duckdb
        import json as _json
        conn = duckdb.connect(os.environ.get("DATABASE_PATH", "data/oracle.duckdb"), read_only=True)
        rows = conn.execute(
            "SELECT port_id, data_source, live_detail FROM port_metrics ORDER BY port_id"
        ).fetchall()
        paired: set[str] = set()
        try:
            paired = set(
                r[0] for r in conn.execute(
                    "SELECT port_id FROM calibration_pairs WHERE matched=1"
                ).fetchall()
            )
        except Exception:
            paired = set()
        out = []
        for pid, ds, ld in rows:
            live = ds is not None and ds.startswith("live:")
            queue_observable = False
            if ld:
                try:
                    detail = _json.loads(ld)
                    queue_observable = bool(detail.get("ao_largo"))
                except Exception:
                    queue_observable = False
            has_pair = pid in paired
            if live and queue_observable and has_pair:
                grade = "VALIDATED"
                label = "validated_live"
            elif live:
                grade = "CONDITIONAL"
                label = "live_observation"
            else:
                grade = "REFERENCE"
                label = "reference_seed"
            out.append({
                "port_id": pid,
                "live": live,
                "grade": grade,
                "label": label,
                "source": ds or "none",
                "queue_observable": queue_observable,
                "paired": has_pair,
            })
        try:
            conn.close()
        except Exception:
            pass
        return out
    except Exception:
        return []

def _persist_now() -> None:
    """Grava o estado dos contadores em disco para sobreviver a restarts/deploys."""
    import os
    try:
        with _lock:
            state = {
                "counts": dict(_counts),
                "uniq": {k: sorted(v) for k, v in _uniq.items()},
                "machines": {k: dict(cnt) for k, cnt in _machines.items()},
                "paths": dict(_paths),
                "tools": dict(_tools),
                "ports": dict(_ports),
                "mcp_total": _mcp_total,
                "mcp_errors": _mcp_errors,
                "errors_total": _errors_total,
                "paid_plans": dict(_paid_plans),
                "paid_users": sorted(_paid_users),
                "decision_denials": _decision_denials,
                "quota_denials": _quota_denials,
                "trial_keys_issued": _trial_keys_issued,
                "events": list(_recent_events),
                "mcp_consumers": dict(_mcp_consumers),
                "mcp_consumer_ips": sorted(_mcp_consumer_ips),
                "machine_stages": {k: sorted(v) for k, v in _MACHINE_STAGES.items()},
                "machine_first": dict(_MACHINE_FIRST),
                "machine_last": dict(_MACHINE_LAST),
                "machine_calls": dict(_MACHINE_CALLS),
                "machine_tool_ts": {k: list(v) for k, v in _MACHINE_TOOL_TS.items()},
                "machine_tool_names": {k: dict(v) for k, v in _MACHINE_TOOL_NAMES.items()},
                "machine_tool_ports": {k: dict(v) for k, v in _MACHINE_TOOL_PORTS.items()},
                "machine_intent": {k: dict(v) for k, v in _MACHINE_INTENT.items()},
                "machine_role": dict(_MACHINE_ROLE),
                "machine_ua": dict(_MACHINE_UA),
                "last_tool_call": _last_tool_call,
                "tool_errors": list(_tool_errors),
                "saved_at": int(time.time()),
            }
        os.makedirs(os.path.dirname(os.path.abspath(_STATE_PATH)), exist_ok=True)
        with open(_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception as e:
        logger.warning("metrics persist failed: %s", e)


def _load_state() -> None:
    """Recarrega o estado persistido no boot (se existir).

    POLÍTICA DE SNAPSHOTS INCOMPLETOS:
    1. Chaves não encontradas no arquivo JSON preservam o estado que já estiver
       na memória. Nenhuma estrutura é zerada a menos que a chave conste no snapshot.
    2. Valores numéricos opcionais como `last_tool_call` mantêm seu estado
       atual se não forem enviados ou se retornarem None no fallback.
    """
    global _mcp_total, _mcp_errors, _errors_total, _last_tool_call, _decision_denials, _quota_denials, _trial_keys_issued
    try:
        import os
        if not os.path.exists(_STATE_PATH):
            return
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)

        if not isinstance(state, dict):
            raise ValueError("Snapshot is not a JSON object")

        # 1. Validar e construir o estado em variáveis temporárias
        # Dicts
        n_counts = dict(state.get("counts", {}))
        n_paths = dict(state.get("paths", {}))
        n_tools = dict(state.get("tools", {}))
        n_ports = dict(state.get("ports", {}))
        n_paid_plans = dict(state.get("paid_plans", {}))
        n_mcp_consumers = dict(state.get("mcp_consumers", {}))
        n_machine_first = dict(state.get("machine_first", {}))
        n_machine_last = dict(state.get("machine_last", {}))
        n_machine_calls = dict(state.get("machine_calls", {}))
        n_machine_role = dict(state.get("machine_role", {}))
        n_machine_ua = dict(state.get("machine_ua", {}))

        # Sets
        n_uniq = {k: set(v) for k, v in state.get("uniq", {}).items()}
        n_machine_stages = {k: set(v) for k, v in state.get("machine_stages", {}).items()}
        n_paid_users = set(state.get("paid_users", []))
        n_mcp_consumer_ips = set(state.get("mcp_consumer_ips", []))

        # Counters
        n_machines = {k: collections.Counter(v) for k, v in state.get("machines", {}).items()}
        n_machine_tool_names = {k: collections.Counter(v) for k, v in state.get("machine_tool_names", {}).items()}
        n_machine_tool_ports = {k: collections.Counter(v) for k, v in state.get("machine_tool_ports", {}).items()}
        n_machine_intent = {k: collections.Counter(v) for k, v in state.get("machine_intent", {}).items()}

        # Lists
        n_machine_tool_ts = {k: list(v) for k, v in state.get("machine_tool_ts", {}).items()}
        n_tool_errors = list(state.get("tool_errors", []) or [])
        events = list(state.get("events", []))
        n_recent_events = events[-100:] if events else []

        # Scalars
        n_mcp_total = int(state.get("mcp_total", _mcp_total))
        n_mcp_errors = int(state.get("mcp_errors", _mcp_errors))
        n_errors_total = int(state.get("errors_total", _errors_total))
        n_decision_denials = int(state.get("decision_denials", _decision_denials))
        n_quota_denials = int(state.get("quota_denials", _quota_denials))
        n_trial_keys_issued = int(state.get("trial_keys_issued", _trial_keys_issued))
        n_last_tool_call = state.get("last_tool_call", _last_tool_call)

        # 2. Substituir o estado global de maneira consistente (Atomic Replacement)
        with _lock:
            if "counts" in state: _counts.clear(); _counts.update(n_counts)
            if "paths" in state: _paths.clear(); _paths.update(n_paths)
            if "tools" in state: _tools.clear(); _tools.update(n_tools)
            if "ports" in state: _ports.clear(); _ports.update(n_ports)
            if "paid_plans" in state: _paid_plans.clear(); _paid_plans.update(n_paid_plans)
            if "mcp_consumers" in state: _mcp_consumers.clear(); _mcp_consumers.update(n_mcp_consumers)
            if "machine_first" in state: _MACHINE_FIRST.clear(); _MACHINE_FIRST.update(n_machine_first)
            if "machine_last" in state: _MACHINE_LAST.clear(); _MACHINE_LAST.update(n_machine_last)
            if "machine_calls" in state: _MACHINE_CALLS.clear(); _MACHINE_CALLS.update(n_machine_calls)
            if "machine_role" in state: _MACHINE_ROLE.clear(); _MACHINE_ROLE.update(n_machine_role)
            if "machine_ua" in state: _MACHINE_UA.clear(); _MACHINE_UA.update(n_machine_ua)

            if "uniq" in state: _uniq.clear(); _uniq.update(n_uniq)
            if "machine_stages" in state: _MACHINE_STAGES.clear(); _MACHINE_STAGES.update(n_machine_stages)
            if "paid_users" in state: _paid_users.clear(); _paid_users.update(n_paid_users)
            if "mcp_consumer_ips" in state: _mcp_consumer_ips.clear(); _mcp_consumer_ips.update(n_mcp_consumer_ips)

            if "machines" in state: _machines.clear(); _machines.update(n_machines)
            if "machine_tool_names" in state: _MACHINE_TOOL_NAMES.clear(); _MACHINE_TOOL_NAMES.update(n_machine_tool_names)
            if "machine_tool_ports" in state: _MACHINE_TOOL_PORTS.clear(); _MACHINE_TOOL_PORTS.update(n_machine_tool_ports)
            if "machine_intent" in state: _MACHINE_INTENT.clear(); _MACHINE_INTENT.update(n_machine_intent)

            if "machine_tool_ts" in state: _MACHINE_TOOL_TS.clear(); _MACHINE_TOOL_TS.update(n_machine_tool_ts)

            # For lists that we maintain globally
            if "tool_errors" in state:
                _tool_errors.clear()
                _tool_errors.extend(n_tool_errors)
            if "events" in state:
                _recent_events.clear()
                _recent_events.extend(n_recent_events)

            _mcp_total = n_mcp_total
            _mcp_errors = n_mcp_errors
            _errors_total = n_errors_total
            _decision_denials = n_decision_denials
            _quota_denials = n_quota_denials
            _trial_keys_issued = n_trial_keys_issued
            if _last_tool_call is None:
                _last_tool_call = n_last_tool_call

        logger.info("metrics state loaded from %s", _STATE_PATH)
    except Exception as e:
        logger.warning("metrics state load failed: %s", e)


def start_persistence(interval: int | None = None) -> None:
    """Inicia o thread de persistência periódica (chamado no boot da API)."""
    global _persist_thread, _window_base
    interval = interval or _STATE_INTERVAL
    _load_state()
    # Baseline da janela do processo atual (para distinguir CURRENT WINDOW de LIFETIME).
    _window_base = {
        "mcp_total": _mcp_total,
        "requests": sum(_counts.values()),
    }
    if _persist_thread and _persist_thread.is_alive():
        return

    def _loop():
        while not _persist_stop.is_set():
            _persist_stop.wait(interval)
            if _persist_stop.is_set():
                break
            _persist_now()

    _persist_thread = threading.Thread(target=_loop, daemon=True, name="metrics-persist")
    _persist_thread.start()
    logger.info("metrics persistence started (interval %ss, path %s)", interval, _STATE_PATH)


def stop_persistence() -> None:
    """Encerra a persistência, gravando o estado final (shutdown)."""
    global _persist_thread
    _persist_stop.set()
    if _persist_thread and _persist_thread.is_alive():
        _persist_thread.join(timeout=5)
    _persist_now()
    logger.info("metrics persistence stopped; final state saved")
