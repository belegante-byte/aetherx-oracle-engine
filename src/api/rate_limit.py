"""Rate limiting por IP para endpoints públicos.

MITIGAÇÃO (auditoria 2026-09-21): observação em /v1/* e /mcp é gratuita por
design, o que expõe o serviço a abuso/DoS. Este middleware aplica uma janela
deslizante por IP com limites generosos e configuração via ambiente:

    RATE_LIMIT_PER_MINUTE       (padrão 300/min por IP — /v1/* e demais rotas)
    RATE_LIMIT_MCP_PER_MINUTE   (padrão 120/min por IP — /mcp)
    RATE_LIMIT_DISABLED=1       desliga (não recomendado em produção)

Clientes autenticados não são limitados: proxy secret (monitoramento/Control
Tower/tests) e Authorization Bearer (M2M decision tools).
"""

import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class PublicRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        default_limit_per_minute: int = 300,
        mcp_limit_per_minute: int = 120,
    ):
        super().__init__(app)
        self._limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", str(default_limit_per_minute)))
        self._mcp_limit = int(os.getenv("RATE_LIMIT_MCP_PER_MINUTE", str(mcp_limit_per_minute)))
        self._disabled = os.getenv("RATE_LIMIT_DISABLED", "0").strip().lower() in {"1", "true", "yes"}
        # {(ip, janela_minuto, grupo): count}
        self._hits: dict[tuple, int] = {}

    async def dispatch(self, request, call_next):
        if self._disabled:
            return await call_next(request)

        # Requisições autenticadas (monitoramento / M2M decision) não pagam o limite.
        if request.headers.get("x-rapidapi-proxy-secret"):
            return await call_next(request)
        auth = request.headers.get("authorization", "") or ""
        if auth.strip().lower().startswith("bearer "):
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        path = request.url.path
        is_mcp = path.startswith("/mcp")
        limit = self._mcp_limit if is_mcp else self._limit
        window = int(time.monotonic() // 60)
        key = (ip, window, "mcp" if is_mcp else "rest")

        count = self._hits.get(key, 0)
        if count >= limit:
            return JSONResponse(
                {"detail": "Too many requests. Reduce the call rate and try again."},
                status_code=429,
            )
        self._hits[key] = count + 1

        # Limpeza aproximada quando o dict infla (descarta janelas antigas).
        if len(self._hits) > 100_000:
            cutoff = int(time.monotonic() // 60)
            self._hits = {k: v for k, v in self._hits.items() if k[1] >= cutoff - 2}

        return await call_next(request)