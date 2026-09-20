import json
import logging
import uuid
from datetime import datetime, timezone
from src.runtime.contracts.v1 import UsageEvent, ClientContext

logger = logging.getLogger("m2m_runtime_metering")


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
    
    # Log estruturado da telemetria
    logger.info(json.dumps(event.model_dump()))
    return event
