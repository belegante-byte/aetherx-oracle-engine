"""Quota diária de observação gratuita para tools de dados do /mcp.

POLÍTICA DE MONETIZAÇÃO (P1):
  - Tools de decisão exigem credencial M2M (gate no M2MGatewayMiddleware);
  - Tools de observação são gratuitas com quota diária por IP, visando
    transformar "anon → trial key" (request_m2m_key) sem punir descoberta.
  - Clientes autenticados (Bearer válido) e o proxy secret ignoram a quota.

Contadores em memória (janela por dia UTC). Ao reiniciar o processo a quota
zera — comportamento aceitável para v1 e documentado.
"""

import os
import threading
from datetime import datetime, timezone

OBSERVATION_QUOTA_PER_DAY = int(os.getenv("MCP_OBSERVATION_QUOTA_PER_DAY", "60"))

_daily: dict[tuple[str, str], int] = {}
_lock = threading.Lock()


def observation_quota_remaining(ip: str, limit: int | None = None) -> int:
    """Quantas chamadas de observation o IP ainda pode fazer hoje."""
    limit = OBSERVATION_QUOTA_PER_DAY if limit is None else limit
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _lock:
        used = _daily.get((ip, day), 0)
    return max(limit - used, 0)


def consume_observation_quota(ip: str, limit: int | None = None) -> tuple[bool, int]:
    """Registra uma chamada de observation do IP; retorna (permitida, restante)."""
    limit = OBSERVATION_QUOTA_PER_DAY if limit is None else limit
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = (ip, day)
    with _lock:
        used = _daily.get(key, 0)
        if used >= limit:
            return False, 0
        _daily[key] = used + 1
        return True, max(limit - used - 1, 0)