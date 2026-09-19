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
# M2M (ex.: SentinelOracle, mcpbeat, Googlebot). São medidos à parte em "bot".
_BOT_TOKENS = (
    "sentineloracle", "mcpbeat", "googlebot", "bingbot", "slurp",
    "duckduckbot", "baiduspider", "yandex", "lighthouse", "gtmetrix",
    "uptimerobot", "pingdom", "statuscake", "monitoring", "pingbot",
    "facebookexternalhit", "twitterbot", "linkedinbot",
)

# Firma de user-agent indica máquina (bot/agente/cliente HTTP), não humano.
_MACHINE_TOKENS = (
    "bot", "spider", "crawl", "curl", "httpx", "requests", "aiohttp",
    "go-http-client", "node-fetch", "axios", "okhttp", "wget", "java",
    "claude", "gpt", "openai", "google-cloud", "browsermob",
)

# Token do próprio projeto: ignora chamadas de nossos próprios health-check.
_SELF_TOKENS = ("belegante-aetherx",)

_lock = threading.Lock()
_counts = {}      # {channel: int}
_uniq = {}        # {channel: set[str]}   hash do IP do cliente
_machines = {}    # {channel: collections.Counter[str]}  chamadas por máquina
_paths = {}       # {path: int}
_t0 = time.time()

# ---- Control Tower: uso de produto (tool, porto, status, latência) ----
_tools = {}            # {tool_name: int}
_ports = {}            # {port_id: int}
_recent_events = collections.deque(maxlen=100)  # [{ts, kind, detail}]
_mcp_errors = 0        # total de erros em invocações de tool
_mcp_total = 0         # total de invocações de tool
_errors_total = 0      # erros HTTP (5xx) observados

_EVENT_KINDS = ("mcp_call", "tool_call", "new_machine", "repeat_machine", "port_query", "error")


def record_tool_call(tool: str, port_id: str | None = None, ok: bool = True, latency_ms: int | None = None) -> None:
    """Registra uma invocação de tool MCP (ou de produto) para a Control Tower."""
    global _mcp_total, _mcp_errors
    with _lock:
        _mcp_total += 1
        _tools[tool] = _tools.get(tool, 0) + 1
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

            async def send_wrapper(message):
                if message.get("type") == "http.response.start":
                    status_holder["status"] = message.get("status")
                await send(message)

            record_http(scope, status_holder=status_holder)
            await self.app(scope, receive, send_wrapper)
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
    if not channel:
        return
    key = _bucket(_client_ip(headers, scope))
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
        }