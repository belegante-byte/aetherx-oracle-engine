import contextvars
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from src.runtime.contracts.v1 import UsageEvent, ClientContext

logger = logging.getLogger("m2m_runtime_metering")

# Permite à camada de tool (mcp_app) associar o client_id à invocação sem
# acoplar ao middleware HTTP — útil p/ auditabilidade de erros no metering.
current_client_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "m2m_current_client_id", default=None
)


def _mask_client_id(client_id: str) -> str:
    """Não grava PII (nome/email do cliente) em logs estruturados.

    Um sha256 curto permite correlacionar eventos por cliente no log sem expor
    a identidade.
    """
    if not client_id:
        return ""
    return "m2m_" + hashlib.sha256(client_id.encode("utf-8")).hexdigest()[:16]


def record_usage(
    context: ClientContext,
    product: str,
    tool: str,
    duration_ms: int,
    status_code: int = 200
) -> UsageEvent:
    """Registra evento de uso M2M para telemetria e futuro billing."""
    req_id = f"req_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    event = UsageEvent(
        request_id=req_id,
        client_id=context.client_id,
        product=product,
        tool=tool,
        access_mode=context.access_mode,
        timestamp=now,
        duration_ms=duration_ms,
        status_code=status_code
    )
    
    # Log estruturado da telemetria — client_id MASCARADO (PII fora do log).
    payload = event.model_dump()
    payload["client_id"] = _mask_client_id(event.client_id)
    logger.info(json.dumps(payload))
    return event
