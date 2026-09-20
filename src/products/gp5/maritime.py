import os
import duckdb
from typing import List, Dict, Any
from dotenv import load_dotenv

from src.runtime.identity import create_entity
from src.runtime.provenance import build_evidence
from src.runtime.events import build_physical_event, create_change_packet
from src.runtime.contracts.v1 import PhysicalEvent, ChangePacket, StateTransition

load_dotenv("config/.env")
RAW_DB = os.getenv("RAW_DATABASE_PATH", "data/processed/aether_oracle.duckdb")


def get_port_physical_events(port_id: str) -> ChangePacket:
    """Adapta observações puras de navios e vagões do DuckDB em um ChangePacket v1 GP5."""
    port_id = port_id.upper()
    events: List[PhysicalEvent] = []
    
    if not os.path.exists(RAW_DB):
        return create_change_packet([])
        
    try:
        conn = duckdb.connect(RAW_DB, read_only=True)
    except duckdb.Error:
        return create_change_packet([])
        
    try:
        # 1. Observação Marítima (Navios)
        ships = conn.execute(
            """
            SELECT imo, vessel_name, status, cargo, dwt, source, ingested_at
            FROM raw_port_lineup
            WHERE port_id = ?
            """, [port_id]
        ).fetchall()
        
        for imo, name, status, cargo, dwt, source, ingested in ships:
            vessel_entity = create_entity(
                entity_type="vessel",
                entity_id=imo or f"UNKNOWN_{name}",
                attributes={
                    "name": name,
                    "dwt_capacity": dwt or 0.0,
                    "observed_cargo": cargo or "UNKNOWN",
                    "cargo_quantity_status": "UNMEASURED_DWT_CAPACITY_ONLY",
                    "port_id": port_id
                }
            )
            evidence = build_evidence(
                source=source or "maritime_authority",
                timestamp=str(ingested) if ingested else None
            )
            
            # Evento temporal de estado
            evt = build_physical_event(
                event_type="VESSEL_STATUS_OBSERVED",
                entity=vessel_entity,
                transition=StateTransition(
                    field="status",
                    from_value=None,
                    to_value=status
                ),
                evidence=[evidence],
                observed_at=str(ingested) if ingested else None
            )
            events.append(evt)
            
        # 2. Observação Terrestre (Vagões Rumo / Land Queue)
        try:
            land_rows = conn.execute(
                """
                SELECT train_id, terminal, commodity, wagons, status, source, ingested_at
                FROM raw_land_queue
                WHERE port_id = ?
                """, [port_id]
            ).fetchall()
            
            for t_id, term, comm, wag, st, source, ingested in land_rows:
                train_entity = create_entity(
                    entity_type="train",
                    entity_id=t_id,
                    attributes={
                        "terminal": term,
                        "commodity": comm,
                        "wagons_count": wag,
                        "status": st,
                        "port_id": port_id
                    }
                )
                evidence = build_evidence(
                    source=source or "railway_operator",
                    timestamp=str(ingested) if ingested else None
                )
                evt = build_physical_event(
                    event_type="LAND_QUEUE_UPDATED",
                    entity=train_entity,
                    transition=StateTransition(
                        field="wagons",
                        from_value=0,
                        to_value=wag
                    ),
                    evidence=[evidence],
                    observed_at=str(ingested) if ingested else None
                )
                events.append(evt)
        except duckdb.Error:
            pass
            
    finally:
        conn.close()
        
    return create_change_packet(events)
