import pytest
import json
from datetime import datetime, timezone

from src.reconstruction.models import ShipmentReconstruction, RichEvidence, EpistemicState, EntityRef, OperationalOrder
from src.reconstruction.engine import ReconstructionEngine
from src.reconstruction.extractor import OrderExtractor

# Simulating the real JSON response obtained from assess_logistics_disruption
MOCK_BRSSZ_RESPONSE = {
  "status": "complete",
  "subject": {
    "port_id": "BRSSZ",
    "objective": "demurrage_avoidance"
  },
  "generated_at": "2026-10-02 16:31:57 UTC",
  "data_quality": {
    "classification": "live_unverified_time",
    "source": "Lachmann",
    "source_observed_at": None,
    "retrieved_at": "2026-10-02T16:28:00Z",
    "age_seconds": None,
    "provenance": "unknown"
  },
  "observations": [
    {
      "fact": "Port BRSSZ status: NORMAL, Delayed: False, ETA Delay Days: 0.2",
      "source": "live:santos+santos_painel",
      "observed_at": "2026-10-02 16:28:31"
    }
  ],
  "provenance": [
    {
      "tool": "calculate_port_risk",
      "source": "live:santos+santos_painel",
      "observed_at": "2026-10-02 16:28:31",
      "classification": "observation"
    }
  ]
}

def test_extract_brssz_live():
    # 1. Create the OperationalOrder
    order = OperationalOrder(
        order_id="ord_brssz_001",
        consumer="agent_test",
        issued_at="2026-10-02T16:31:57Z",
        objective="demurrage_avoidance",
        parameters={"port_id": "BRSSZ"}
    )
    
    # 2. Extract Evidence
    evidences = OrderExtractor.extract_from_assess_logistics(order, MOCK_BRSSZ_RESPONSE)
    
    assert len(evidences) == 2 # origin_port, and status
    
    # origin_port evidence
    port_ev = next(e for e in evidences if e.claim_field == "origin_port")
    assert port_ev.claim_value == "BRSSZ"
    assert port_ev.epistemic_state == EpistemicState.OBSERVED
    assert port_ev.source == "operational_order"
    
    # status evidence
    status_ev = next(e for e in evidences if e.claim_field == "status")
    assert "ETA Delay Days: 0.2" in status_ev.claim_value
    assert status_ev.epistemic_state == EpistemicState.OBSERVED # live_unverified_time
    assert status_ev.source == "live:santos+santos_painel"
    assert status_ev.source_observed_at == "2026-10-02 16:28:31"
    assert status_ev.origin_order_id == "ord_brssz_001"
    
    # 3. Build Partial ShipmentReconstruction
    engine = ReconstructionEngine()
    shipment = ShipmentReconstruction(shipment_id="shp_test_001")
    
    for ev in evidences:
        shipment = engine.apply_evidence(shipment, ev)
        
    # Check fields
    assert shipment.origin_port.current_value == "BRSSZ"
    assert shipment.origin_port.state == EpistemicState.OBSERVED
    assert len(shipment.origin_port.supporting_evidence_ids) == 1
    
    assert shipment.status.current_value == "Port BRSSZ status: NORMAL, Delayed: False, ETA Delay Days: 0.2"
    
    # 4. Invariants Verification
    
    # UNKNOWN remains UNKNOWN
    assert shipment.cargo.current_value is None
    assert shipment.cargo.state == EpistemicState.UNKNOWN
    
    assert shipment.vessel.current_value is None
    assert shipment.shipper.current_value is None
    
    # Provenance is retrievable
    stored_ev = shipment.evidence_store[port_ev.logical_id]
    assert stored_ev.retrieved_at is not None
    assert stored_ev.origin_order_id == "ord_brssz_001"

def test_missing_timestamp_remains_null():
    order = OperationalOrder(
        order_id="ord_null_ts",
        consumer="agent",
        issued_at="2026-10-02T16:00:00Z",
        objective="routing",
        parameters={"port_id": "BRSSZ"}
    )
    
    mock_no_ts = dict(MOCK_BRSSZ_RESPONSE)
    mock_no_ts["data_quality"]["source_observed_at"] = None
    mock_no_ts["provenance"][0]["observed_at"] = None
    
    evs = OrderExtractor.extract_from_assess_logistics(order, mock_no_ts)
    status_ev = next(e for e in evs if e.claim_field == "status")
    
    # Invariant: don't invent timestamps
    assert status_ev.source_observed_at is None
    
def test_derived_evidence_does_not_become_observed():
    order = OperationalOrder(
        order_id="ord_derived",
        consumer="agent",
        issued_at="2026-10-02T16:00:00Z",
        objective="routing",
        parameters={"port_id": "CNTAO"}
    )
    
    mock_derived = dict(MOCK_BRSSZ_RESPONSE)
    mock_derived["data_quality"]["classification"] = "modeled"
    
    evs = OrderExtractor.extract_from_assess_logistics(order, mock_derived)
    status_ev = next(e for e in evs if e.claim_field == "status")
    
    # Invariant: derived/modeled stays DERIVED, not OBSERVED
    assert status_ev.epistemic_state == EpistemicState.DERIVED
