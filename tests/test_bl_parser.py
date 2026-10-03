import pytest
from datetime import datetime, timezone
import uuid

from src.ingestion.bl_parser import parse_bl_static
from src.reconstruction.models import (
    EpistemicState, 
    ShipmentReconstruction, 
    RichEvidence, 
    EntityRef
)
from src.reconstruction.engine import ReconstructionEngine
from src.reconstruction.economic_value import assess_economic_value

def test_parse_bl_completo_todos_observed():
    payload = {
        "vessel": "M/V Test",
        "cargo": "Soja",
        "consignee": "AgriCorp SA",
        "destination": "CNQIN",
        "quantity": 60000,
        "shipper": "Export BR",
        "bl_number": "BL12345",
        "issue_date": "2026-10-01"
    }
    
    parsed = parse_bl_static(payload)
    
    assert parsed["consignee"][1] == EpistemicState.OBSERVED
    assert parsed["destination_port"][1] == EpistemicState.OBSERVED
    assert parsed["consignee"][0] == "AgriCorp SA"
    assert "cargo_volume" not in parsed

def test_parse_bl_parcial_ausentes_unknown():
    payload = {
        "vessel": "M/V Test"
    }
    
    parsed = parse_bl_static(payload)
    
    assert parsed["consignee"][1] == EpistemicState.UNKNOWN
    assert parsed["destination_port"][1] == EpistemicState.UNKNOWN
    assert parsed["consignee"][0] is None

def test_integracao_shipment_reconstruction_commercial_readiness():
    payload = {
        "vessel": "CL HENGYANG",
        "cargo": "CLORETO DE POTASSIO (FERTILIZANTE)",
        "consignee": "Agro Import SA",
        "destination": "BRSSZ",
        "quantity": 50000
    }
    parsed = parse_bl_static(payload)
    
    s = ShipmentReconstruction(shipment_id="shp_test_bl")
    engine = ReconstructionEngine()
    now = datetime.now(timezone.utc).isoformat()
    
    engine.apply_evidence(s, RichEvidence(
        evidence_id="ev_port", claim_field="port_call", claim_value="BRSSZ",
        entity=EntityRef(type="shipment", raw_name="shp_test_bl"),
        epistemic_state=EpistemicState.OBSERVED, source="santos_painel", retrieved_at=now
    ))
    engine.apply_evidence(s, RichEvidence(
        evidence_id="ev_status", claim_field="status", claim_value="MODERATE DELAY, DELAYED: TRUE",
        entity=EntityRef(type="shipment", raw_name="shp_test_bl"),
        epistemic_state=EpistemicState.OBSERVED, source="santos_painel", retrieved_at=now
    ))

    for field, (val, state, prov) in parsed.items():
        if state == EpistemicState.OBSERVED:
            ev = RichEvidence(
                evidence_id=f"ev_bl_{field}_{uuid.uuid4().hex[:8]}", 
                claim_field=field, 
                claim_value=val,
                entity=EntityRef(type="shipment", raw_name="shp_test_bl"),
                epistemic_state=state, 
                source=prov,
                retrieved_at=now
            )
            # Sem o try/except silencioso: se lançar exceção, o teste falha.
            engine.apply_evidence(s, ev)
                
    a = assess_economic_value(s)
    assert a.commercial_readiness == "identified"
