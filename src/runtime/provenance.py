from typing import Optional
from datetime import datetime, timezone
from src.runtime.contracts.v1 import Evidence


def build_evidence(source: str, raw_payload: Optional[str] = None, confidence: float = 1.0, timestamp: Optional[str] = None) -> Evidence:
    """Constrói um registro auditável de evidência e proveniência."""
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return Evidence(
        source=str(source).strip(),
        timestamp=ts,
        raw_payload=raw_payload,
        confidence=confidence
    )
