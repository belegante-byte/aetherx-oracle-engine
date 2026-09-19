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

# ---- Monetização: assinantes pagos vistos via gateway RapidAPI ----
_paid_plans = {}      # {plan_name: int}  chamadas por tier pago (PRO/ULTRA/MEGA/CUSTOM)
_paid_users = set()   # set[str]          X-RapidAPI-User distintos em plano pago

PAID_PLANS = ("PRO", "ULTRA", "MEGA", "CUSTOM")

# ---- Consumidores reais: máquinas que EXECUTARAM pelo menos uma tool ----
# Distingue "consumo real do Oracle" de "handshake/liveness de crawlers".
# `_mcp_consumers` registra ip_hash de máquinas que invocaram tools/call.
_mcp_consumers = {}    # {ip_hash: int}  tools executadas por máquina
_mcp_consumer_ips = set()  # set[str]

# ---- Funil M2M por máquina anônima ----
# Cada máquina (ip_hash) tem os estágios do funil comportamental que atingiu:
#   discovery -> mcp_connect -> tool_call -> repeat -> paid
# Agregado no snapshot como funnel; a Control Tower mostra máquinas individuais.
_MACHINE_STAGES = {}    # {ip_hash: set[str]}  estágios atingidos
_MACHINE_FIRST = {}     # {ip_hash: int}  ts do primeiro contato
_MACHINE_LAST = {}      # {ip_hash: int}  ts do último contato
_MACHINE_CALLS = {}     # {ip_hash: int}  total de chamadas (qualquer canal)

FUNNEL_STAGES = ("discovery", "mcp_connect", "tool_call", "repeat", "paid")


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


def _classify_stage(path: str, channel: str) -> str | None:
    """Mapeia uma requisição para o estágio do funil que ela representa."""
    if path in _DISCOVERY_PATHS or path.startswith("/port-congestion-") or path == "/":
        return "discovery"
    if channel == "mcp":
        return "mcp_connect"
    if channel == "rest":
        return None  # REST usa o estágio 'paid' via subscription; consumo via tool
    return None

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


def record_tool_call(tool: str, port_id: str | None = None, ok: bool = True, latency_ms: int | None = None) -> None:
    """Registra uma invocação de tool MCP (ou de produto) para a Control Tower."""
    global _mcp_total, _mcp_errors
    mid = get_current_machine()
    if mid:
        _mark_stage(mid, "tool_call")
    with _lock:
        _mcp_total += 1
        _tools[tool] = _tools.get(tool, 0) + 1
        if mid:
            _mcp_consumers[mid] = _mcp_consumers.get(mid, 0) + 1
            _mcp_consumer_ips.add(mid)
        if port_id:
            _ports[port_id] = _ports.get(port_id, 0) + 1
            _recent_events.appendleft({
                "ts": int(time.time()),
                "kind": "port_query",
                "detail": port_id,
            })
        if not ok:
            _mcp_errors += 1
        _recent_events.appendleft({
            "ts": int(time.time()),
            "kind": "tool_call",
            "detail": tool,
            "ok": ok,
            "latency_ms": latency_ms,
        })


def record_error() -> None:
    """Registra um erro HTTP 5xx (para a taxa de erro geral)."""
    global _errors_total
    with _lock:
        _errors_total += 1


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
            _mark_stage(key, "repeat")
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
            # Monetização
            "paid_plans": dict(_paid_plans),
            "paid_users": sorted(_paid_users),
            "paid_user_count": len(_paid_users),
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
                }
                for mid in sorted(_MACHINE_STAGES.keys(),
                                 key=lambda m: -_MACHINE_CALLS.get(m, 0))[:12]
            ],
        }

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
                "events": list(_recent_events),
                "mcp_consumers": dict(_mcp_consumers),
                "mcp_consumer_ips": sorted(_mcp_consumer_ips),
                "machine_stages": {k: sorted(v) for k, v in _MACHINE_STAGES.items()},
                "machine_first": dict(_MACHINE_FIRST),
                "machine_last": dict(_MACHINE_LAST),
                "machine_calls": dict(_MACHINE_CALLS),
                "saved_at": int(time.time()),
            }
        os.makedirs(os.path.dirname(os.path.abspath(_STATE_PATH)), exist_ok=True)
        with open(_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception as e:
        logger.warning("metrics persist failed: %s", e)


def _load_state() -> None:
    """Recarrega o estado persistido no boot (se existir)."""
    global _mcp_total, _mcp_errors, _errors_total
    try:
        import os
        if not os.path.exists(_STATE_PATH):
            return
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
        with _lock:
            _counts.update(state.get("counts", {}))
            for k, v in state.get("uniq", {}).items():
                _uniq.setdefault(k, set()).update(v)
            for k, v in state.get("machines", {}).items():
                _machines.setdefault(k, collections.Counter()).update(v)
            _paths.update(state.get("paths", {}))
            _tools.update(state.get("tools", {}))
            _ports.update(state.get("ports", {}))
            _mcp_total = state.get("mcp_total", _mcp_total)
            _mcp_errors = state.get("mcp_errors", _mcp_errors)
            _errors_total = state.get("errors_total", _errors_total)
            _paid_plans.update(state.get("paid_plans", {}))
            _paid_users.update(state.get("paid_users", []))
            _mcp_consumers.update(state.get("mcp_consumers", {}))
            _mcp_consumer_ips.update(state.get("mcp_consumer_ips", []))
            for k, v in state.get("machine_stages", {}).items():
                _MACHINE_STAGES.setdefault(k, set()).update(v)
            _MACHINE_FIRST.update(state.get("machine_first", {}))
            _MACHINE_LAST.update(state.get("machine_last", {}))
            _MACHINE_CALLS.update(state.get("machine_calls", {}))
            events = state.get("events", [])
            if events:
                _recent_events.extend(events[-100:])
        logger.info("metrics state loaded from %s", _STATE_PATH)
    except Exception as e:
        logger.warning("metrics state load failed: %s", e)


def start_persistence(interval: int | None = None) -> None:
    """Inicia o thread de persistência periódica (chamado no boot da API)."""
    global _persist_thread
    interval = interval or _STATE_INTERVAL
    _load_state()
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
