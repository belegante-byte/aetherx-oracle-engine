import uuid
from typing import List, Optional, Any
from datetime import datetime, timezone
from src.runtime.contracts.v1 import Entity, Evidence, StateTransition, PhysicalEvent, ChangePacket


def build_physical_event(
    event_type: str,
    entity: Entity,
    transition: Optional[StateTransition] = None,
    evidence: Optional[List[Evidence]] = None,
    observed_at: Optional[str] = None
) -> PhysicalEvent:
    """Gera um evento temporal de transição ou primeira observação."""
    ts = observed_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    
    return PhysicalEvent(
        event_id=event_id,
        event_type=str(event_type).strip().upper(),
        entity=entity,
        transition=transition,
        observed_at=ts,
        evidence=evidence or []
    )


def create_change_packet(events: List[PhysicalEvent]) -> ChangePacket:
    """Empacota uma sequência temporal de eventos em um ChangePacket v1."""
    packet_id = f"cp_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return ChangePacket(
        packet_id=packet_id,
        generated_at=now,
        events=events
    )
