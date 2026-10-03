import pytest
from src.reconstruction.models import ShipmentReconstruction, RichEvidence, EpistemicState, EntityRef
from src.reconstruction.engine import ReconstructionEngine
from datetime import datetime, timezone

def test_evidence_idempotency():
    engine = ReconstructionEngine()
    shipment = ShipmentReconstruction(shipment_id="shp_123")
    
    ev = RichEvidence(
        evidence_id="ev_1",
        claim_field="vessel",
        claim_value="VALEMAX 1",
        entity=EntityRef(type="vessel", raw_name="VALEMAX 1"),
        epistemic_state=EpistemicState.OBSERVED,
        source="mock",
        retrieved_at=datetime.now(timezone.utc).isoformat()
    )
    
    shipment = engine.apply_evidence(shipment, ev)
    assert len(shipment.evidence_store) == 1
    assert shipment.vessel.current_value == "VALEMAX 1"
    
    # Aplicar a MESMA evidência novamente não deve duplicar
    shipment = engine.apply_evidence(shipment, ev)
    assert len(shipment.evidence_store) == 1
    assert len(shipment.vessel.supporting_evidence_ids) == 1

def test_epistemological_escalation():
    engine = ReconstructionEngine()
    shipment = ShipmentReconstruction(shipment_id="shp_123")
    
    # Começa com inferência
    ev_inf = RichEvidence(
        evidence_id="ev_inf_1",
        claim_field="vessel",
        claim_value="VALEMAX UNKNOWN",
        entity=EntityRef(type="vessel", raw_name="VALEMAX"),
        epistemic_state=EpistemicState.INFERRED,
        source="mock_model",
        retrieved_at="2026-10-02T10:00:00Z"
    )
    shipment = engine.apply_evidence(shipment, ev_inf)
    assert shipment.vessel.state == EpistemicState.INFERRED
    assert shipment.vessel.current_value == "VALEMAX UNKNOWN"
    
    # Observação real supera inferência
    ev_obs = RichEvidence(
        evidence_id="ev_obs_1",
        claim_field="vessel",
        claim_value="VALE BRASIL",
        entity=EntityRef(type="vessel", raw_name="VALE BRASIL"),
        epistemic_state=EpistemicState.OBSERVED,
        source="ais",
        retrieved_at="2026-10-02T11:00:00Z"
    )
    shipment = engine.apply_evidence(shipment, ev_obs)
    
    assert shipment.vessel.state == EpistemicState.OBSERVED
    assert shipment.vessel.current_value == "VALE BRASIL"
    assert ev_obs.logical_id in shipment.vessel.supporting_evidence_ids

def test_contradiction_handling():
    engine = ReconstructionEngine()
    shipment = ShipmentReconstruction(shipment_id="shp_123")
    
    # Fonte A diz X
    ev_a = RichEvidence(
        evidence_id="ev_a",
        claim_field="origin_port",
        claim_value="BRSSZ",
        entity=EntityRef(type="port", raw_name="Santos"),
        epistemic_state=EpistemicState.OBSERVED,
        source="source_A",
        retrieved_at="2026-10-02T10:00:00Z"
    )
    shipment = engine.apply_evidence(shipment, ev_a)
    
    # Fonte B diz Y no MESMO nível epistêmico
    ev_b = RichEvidence(
        evidence_id="ev_b",
        claim_field="origin_port",
        claim_value="BRPNG",
        entity=EntityRef(type="port", raw_name="Paranagua"),
        epistemic_state=EpistemicState.OBSERVED,
        source="source_B",
        retrieved_at="2026-10-02T10:05:00Z"
    )
    shipment = engine.apply_evidence(shipment, ev_b)
    
    # O motor deve marcar CONTRADICTION
    assert shipment.origin_port.state == EpistemicState.CONTRADICTION
    assert ev_b.logical_id in shipment.origin_port.conflicting_evidence_ids
    # Mantém ambas no store
    assert ev_a.logical_id in shipment.evidence_store
    assert ev_b.logical_id in shipment.evidence_store

def test_evidence_logical_identity():
    # 9. Teste crítico de contaminação: 3 queries da mesma observação geram apenas 1 logical evidence
    engine = ReconstructionEngine()
    shipment = ShipmentReconstruction(shipment_id="shp_test_logical")
    
    # Query 1
    ev_a = RichEvidence(
        evidence_id="ev_random_1",
        claim_field="port",
        claim_value="BRSSZ",
        entity=EntityRef(type="port", id="BRSSZ", raw_name="Santos"),
        epistemic_state=EpistemicState.OBSERVED,
        source="ais",
        source_observed_at="2026-10-02T10:00:00Z",
        retrieved_at="2026-10-02T10:01:00Z",
        origin_order_id="order_1"
    )
    
    # Query 2 (mesma observação, momento diferente de extração/ordem)
    ev_b = RichEvidence(
        evidence_id="ev_random_2",
        claim_field="port",
        claim_value="BRSSZ",
        entity=EntityRef(type="port", id="BRSSZ", raw_name="Santos"),
        epistemic_state=EpistemicState.OBSERVED,
        source="ais",
        source_observed_at="2026-10-02T10:00:00Z",
        retrieved_at="2026-10-02T10:05:00Z",
        origin_order_id="order_2"
    )
    
    # Query 3
    ev_c = RichEvidence(
        evidence_id="ev_random_3",
        claim_field="port",
        claim_value="BRSSZ",
        entity=EntityRef(type="port", id="BRSSZ", raw_name="Santos"),
        epistemic_state=EpistemicState.OBSERVED,
        source="ais",
        source_observed_at="2026-10-02T10:00:00Z",
        retrieved_at="2026-10-02T10:10:00Z",
        origin_order_id="order_3"
    )
    
    engine.apply_evidence(shipment, ev_a)
    engine.apply_evidence(shipment, ev_b)
    engine.apply_evidence(shipment, ev_c)
    
    # Todas colidem no mesmo logical_id, so escrevendo por cima da outra sem inflar o store
    assert len(shipment.evidence_store) == 1
    assert ev_a.logical_id == ev_b.logical_id == ev_c.logical_id

def test_different_sources_same_fact():
    # 10. Teste de fontes diferentes
    engine = ReconstructionEngine()
    shipment = ShipmentReconstruction(shipment_id="shp_test_sources")
    
    ev_ais = RichEvidence(
        evidence_id="ev_ais",
        claim_field="port",
        claim_value="BRSSZ",
        entity=EntityRef(type="port", id="BRSSZ", raw_name="Santos"),
        epistemic_state=EpistemicState.OBSERVED,
        source="ais",
        source_observed_at="2026-10-02T10:00:00Z",
        retrieved_at="2026-10-02T10:01:00Z"
    )
    
    ev_terminal = RichEvidence(
        evidence_id="ev_term",
        claim_field="port",
        claim_value="BRSSZ",
        entity=EntityRef(type="port", id="BRSSZ", raw_name="Santos"),
        epistemic_state=EpistemicState.OBSERVED,
        source="terminal",
        source_observed_at="2026-10-02T10:00:00Z",
        retrieved_at="2026-10-02T10:01:00Z"
    )
    
    engine.apply_evidence(shipment, ev_ais)
    engine.apply_evidence(shipment, ev_terminal)
    
    # Como as fontes diferem, os logical_ids diferem, logo 2 evidências distintas convergem
    assert len(shipment.evidence_store) == 2
