import json
import duckdb
from typing import List, Optional
from src.reconstruction.persistence.schema import create_schema
from src.reconstruction.persistence.serialization import (
    evidence_to_dict, evidence_from_dict, 
    shipment_to_json, shipment_from_json,
    entity_to_json
)
from src.reconstruction.models import RichEvidence, ShipmentReconstruction, VesselEntity, PortCall, Voyage

class ReconstructionRepository:
    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn
        create_schema(self.conn)

    def save_evidence(self, ev: RichEvidence) -> str:
        """Returns 'INSERTED' or 'DEDUPLICATED'"""
        d = evidence_to_dict(ev)
        
        # Check if exists to return explicit DEDUPLICATED status
        res = self.conn.execute("SELECT logical_id FROM evidence_ledger WHERE logical_id = ?", (ev.logical_id,)).fetchone()
        if res:
            return "DEDUPLICATED"
        self.conn.execute("""
            INSERT INTO evidence_ledger (
                logical_id, evidence_id, source, claim_field, claim_value, epistemic_state, 
                confidence, entity, source_observed_at, retrieved_at, origin_order_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (logical_id) DO NOTHING
        """, (
            ev.logical_id, ev.evidence_id, ev.source, ev.claim_field, json.dumps(d['claim_value']), 
            ev.epistemic_state.value, ev.confidence, json.dumps(d['entity']), 
            ev.source_observed_at, ev.retrieved_at, ev.origin_order_id
        ))
        return "INSERTED"

    def mark_tombstone(self, logical_id: str, retrieved_at: str):
        tombstone_id = f"tombstone_{logical_id}_{retrieved_at}"
        self.conn.execute("""
            INSERT INTO evidence_ledger (logical_id, is_tombstone, target_logical_id, retrieved_at, created_at)
            VALUES (?, TRUE, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT DO NOTHING
        """, (tombstone_id, logical_id, retrieved_at))

    def get_active_evidence_for_entity(self, entity_raw_name: str) -> List[RichEvidence]:
        rows = self.conn.execute("""
            SELECT logical_id, evidence_id, source, claim_field, claim_value, epistemic_state, 
                   confidence, entity, source_observed_at, retrieved_at, origin_order_id
            FROM evidence_ledger
            WHERE is_tombstone = FALSE
              AND json_extract_string(entity, '$.raw_name') = ?
              AND logical_id NOT IN (
                  SELECT target_logical_id FROM evidence_ledger WHERE is_tombstone = TRUE AND target_logical_id IS NOT NULL
              )
            ORDER BY created_at ASC
        """, (entity_raw_name,)).fetchall()
        
        evidences = []
        for r in rows:
            d = {
                "evidence_id": r[1],
                "source": r[2],
                "claim_field": r[3],
                "claim_value": json.loads(r[4]),
                "epistemic_state": r[5],
                "confidence": r[6],
                "entity": json.loads(r[7]),
                "source_observed_at": r[8],
                "retrieved_at": r[9],
                "origin_order_id": r[10]
            }
            evidences.append(evidence_from_dict(d))
        return evidences

    def save_shipment(self, shipment: ShipmentReconstruction):
        pc_id = shipment.port_call.current_value if shipment.port_call.current_value else "unknown"
        payload = shipment_to_json(shipment)
        self.conn.execute("""
            INSERT INTO shipment_reconstructions (stable_id, port_call_id, payload)
            VALUES (?, ?, ?)
            ON CONFLICT (stable_id) DO UPDATE SET payload = excluded.payload, port_call_id = excluded.port_call_id
        """, (shipment.stable_id, pc_id, payload))

    def load_shipment(self, stable_id: str) -> Optional[ShipmentReconstruction]:
        res = self.conn.execute("SELECT payload FROM shipment_reconstructions WHERE stable_id = ?", (stable_id,)).fetchone()
        if res:
            return shipment_from_json(res[0])
        return None

    def save_vessel(self, vessel: VesselEntity):
        self.conn.execute("""
            INSERT INTO entities_vessel (stable_id, payload) VALUES (?, ?)
            ON CONFLICT (stable_id) DO UPDATE SET payload = excluded.payload
        """, (vessel.stable_id, entity_to_json(vessel)))
        
    def save_port_call(self, pc: PortCall):
        self.conn.execute("""
            INSERT INTO entities_port_call (stable_id, payload) VALUES (?, ?)
            ON CONFLICT (stable_id) DO UPDATE SET payload = excluded.payload
        """, (pc.stable_id, entity_to_json(pc)))

    def begin_transaction(self):
        self.conn.execute("BEGIN TRANSACTION")
        
    def commit_transaction(self):
        self.conn.execute("COMMIT")
        
    def rollback_transaction(self):
        self.conn.execute("ROLLBACK")
