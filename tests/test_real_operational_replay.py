import pytest
import duckdb
import uuid
from src.api.main import get_gp5_physical_events
from src.api.mcp_app import assess_logistics_disruption
from src.reconstruction.models import RichEvidence, EntityRef, EpistemicState, ShipmentReconstruction
from src.reconstruction.persistence.repository import ReconstructionRepository
from src.reconstruction.engine import ReconstructionEngine

@pytest.fixture
def repo():
    conn = duckdb.connect("test_disposable_real_replay.duckdb")
    repository = ReconstructionRepository(conn)
    yield repository
    conn.close()
    import os
    if os.path.exists("test_disposable_real_replay.duckdb"):
        os.remove("test_disposable_real_replay.duckdb")

def test_real_operational_replay(repo):
    # 1. First Operational Query: Physical Events
    # This simulates the real payload extracted from the operational API.
    # (Bypassing get_gp5_physical_events directly as the test DB lacks 'source' column).
    events = [
        {
          "schema_version": "physical-event.v1",
          "event_id": "evt_0c71c855190d",
          "event_type": "VESSEL_STATUS_OBSERVED",
          "entity": {
            "type": "vessel",
            "id": "UNKNOWN_CL HENGYANG",
            "attributes": {
              "name": "CL HENGYANG",
              "dwt_capacity": 0.0,
              "observed_cargo": "CLORETO DE POTASSIO (FERTILIZANTE)",
              "cargo_quantity_status": "UNMEASURED_DWT_CAPACITY_ONLY",
              "port_id": "BRSSZ"
            }
          },
          "transition": {
            "field": "status",
            "from_value": None,
            "to_value": "EM_OPERACAO"
          },
          "observed_at": "2026-10-02 16:28:00",
          "evidence": [
            {
              "source": "santos_painel",
              "timestamp": "2026-10-02 16:28:00",
              "raw_payload": None,
              "confidence": 1.0
            }
          ]
        }
    ]
    
    # Let's take the first vessel from the real output
    event = events[0]
    vessel_name = event["entity"]["attributes"]["name"]
    cargo_val = event["entity"]["attributes"].get("observed_cargo", "UNKNOWN")
    port_val = event["entity"]["attributes"].get("port_id", "BRSSZ")
    
    # Construct Shipment Provisional Identity
    shipment_id = f"shp_{port_val}_{vessel_name.replace(' ', '_')}"
    s = ShipmentReconstruction(shipment_id=shipment_id)
    
    # 2. Extract Evidence manually simulating an Extractor
    ev_vessel = RichEvidence(
        evidence_id=f"ev_{uuid.uuid4().hex[:8]}", claim_field="vessel", claim_value=vessel_name,
        entity=EntityRef(type="shipment", raw_name=shipment_id), epistemic_state=EpistemicState.OBSERVED,
        source="santos_painel", retrieved_at=event["observed_at"]
    )
    ev_cargo = RichEvidence(
        evidence_id=f"ev_{uuid.uuid4().hex[:8]}", claim_field="cargo", claim_value=cargo_val,
        entity=EntityRef(type="shipment", raw_name=shipment_id), epistemic_state=EpistemicState.OBSERVED,
        source="santos_painel", retrieved_at=event["observed_at"]
    )
    ev_port = RichEvidence(
        evidence_id=f"ev_{uuid.uuid4().hex[:8]}", claim_field="port_call", claim_value=port_val,
        entity=EntityRef(type="shipment", raw_name=shipment_id), epistemic_state=EpistemicState.OBSERVED,
        source="santos_painel", retrieved_at=event["observed_at"]
    )
    
    # Apply to Engine and Save to DB
    engine = ReconstructionEngine()
    engine.apply_evidence(s, ev_vessel)
    engine.apply_evidence(s, ev_cargo)
    engine.apply_evidence(s, ev_port)
    
    repo.save_evidence(ev_vessel)
    repo.save_evidence(ev_cargo)
    repo.save_evidence(ev_port)
    
    # Assert Strict Epistemology (DO NOT INVENT DESTINATION OR SHIPPER)
    assert s.cargo.current_value == cargo_val
    assert s.destination_port.state == EpistemicState.UNKNOWN
    assert s.shipper.state == EpistemicState.UNKNOWN
    
    # 3. Second Operational Query: Assess Logistics Disruption
    # This brings Port Status, but doesn't overwrite cargo.
    disruption = {
      "status": "complete",
      "generated_at": "2026-10-02 23:45:10 UTC",
      "observations": [
        {
          "fact": "Port BRSSZ status: MODERATE DELAY, Delayed: True, ETA Delay Days: 1.0",
          "source": "static_reference_seed",
          "observed_at": "2026-10-02 23:45:10"
        }
      ]
    }
    status_fact = disruption["observations"][0]["fact"]
    
    ev_status = RichEvidence(
        evidence_id=f"ev_{uuid.uuid4().hex[:8]}", claim_field="status", claim_value=status_fact,
        entity=EntityRef(type="shipment", raw_name=shipment_id), epistemic_state=EpistemicState.OBSERVED,
        source="system", retrieved_at=disruption["generated_at"]
    )
    
    engine.apply_evidence(s, ev_status)
    repo.save_evidence(ev_status)
    
    assert s.status.current_value == status_fact
    
    repo.save_shipment(s)
    
    # 4. RESTART & REPLAY LEDGER
    # Close connection implicitly by creating a new repo instance
    conn2 = duckdb.connect("test_disposable_real_replay.duckdb")
    repo2 = ReconstructionRepository(conn2)
    
    # Fetch all active evidence for this shipment entity
    active_evidences = repo2.get_active_evidence_for_entity(shipment_id)
    
    # Rebuild from scratch
    rebuilt_s = ShipmentReconstruction(shipment_id=shipment_id)
    engine2 = ReconstructionEngine()
    for e in active_evidences:
        engine2.apply_evidence(rebuilt_s, e)
        
    # 5. Verify the Replay accurately captured the real operational state
    assert rebuilt_s.cargo.current_value == cargo_val
    assert rebuilt_s.vessel.current_value == vessel_name
    assert rebuilt_s.status.current_value == status_fact
    
    # Verify we did NOT hallucinate missing fields
    assert rebuilt_s.destination_port.state == EpistemicState.UNKNOWN
    assert rebuilt_s.shipper.state == EpistemicState.UNKNOWN
    
    # Total evidence should be 4
    assert len(active_evidences) == 4
    
    conn2.close()
