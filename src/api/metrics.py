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
    """Middleware ASGI: registra a chamada antes de passar para o app."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            record_http(scope)
        await self.app(scope, receive, send)


def record_http(scope) -> None:
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
        _machines.setdefault(channel, collections.Counter())[key] += 1
        _paths[path] = _paths.get(path, 0) + 1
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
        return {
            "uptime_seconds": int(time.time() - _t0),
            "total": dict(_counts),
            "bot_calls": _counts.get("bot", 0),
            "unique_machines": uniq,
            "repeat_machines": repeat,
            "second_call_rate": second_call_rate,
            "top_paths": sorted(_paths.items(), key=lambda x: -x[1])[:20],
        }