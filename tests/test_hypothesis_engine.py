import pytest
from src.reconstruction.models import ShipmentReconstruction, RichEvidence, EpistemicState, EntityRef, ShipmentHypothesis
from src.reconstruction.hypothesis_engine import HypothesisEngine
from src.reconstruction.engine import ReconstructionEngine

@pytest.fixture
def base_shipment():
    return ShipmentReconstruction(shipment_id="shp_1")

@pytest.fixture
def hypothesis_engine():
    return HypothesisEngine()

@pytest.fixture
def engine():
    return ReconstructionEngine()

def test_no_evidence_returns_unknown(base_shipment, hypothesis_engine):
    hyp = hypothesis_engine.evaluate_cargo(base_shipment)
    assert hyp is None
    assert base_shipment.cargo.state == EpistemicState.UNKNOWN

def test_insufficient_evidence_returns_unknown(base_shipment, hypothesis_engine, engine):
    ev_vessel = RichEvidence(
        evidence_id="ev_1", claim_field="vessel.type", claim_value="bulk_carrier",
        entity=EntityRef(type="vessel", raw_name="VALEMAX"), epistemic_state=EpistemicState.OBSERVED,
        source="ais", retrieved_at="2026"
    )
    engine.apply_evidence(base_shipment, ev_vessel)
    
    hyp = hypothesis_engine.evaluate_cargo(base_shipment)
    assert hyp is None

def test_converging_evidence_returns_inferred(base_shipment, hypothesis_engine, engine):
    ev1 = RichEvidence(evidence_id="ev_1", claim_field="vessel.type", claim_value="bulk_carrier", entity=EntityRef(type="vessel", raw_name="A"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    ev2 = RichEvidence(evidence_id="ev_2", claim_field="port_call", claim_value="BRSSZ", entity=EntityRef(type="port", raw_name="Santos"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    ev3 = RichEvidence(evidence_id="ev_3", claim_field="terminal", claim_value="T39", entity=EntityRef(type="terminal", raw_name="T39"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    
    engine.apply_evidence(base_shipment, ev1)
    engine.apply_evidence(base_shipment, ev2)
    engine.apply_evidence(base_shipment, ev3)
    
    hyp = hypothesis_engine.evaluate_cargo(base_shipment)
    assert hyp is not None
    assert hyp.epistemic_state == EpistemicState.INFERRED
    assert hyp.claim_value == "soybeans"
    
    assert hyp.provenance == "hypothesis_engine_v1"
    assert set(hyp.supporting_evidence_ids) == {ev1.logical_id, ev2.logical_id, ev3.logical_id}
    assert not hyp.conflicting_evidence_ids

def test_conflicting_evidence_returns_contradiction(base_shipment, hypothesis_engine, engine):
    ev1 = RichEvidence(evidence_id="ev_1", claim_field="vessel.type", claim_value="tanker", entity=EntityRef(type="vessel", raw_name="B"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    ev2 = RichEvidence(evidence_id="ev_2", claim_field="port_call", claim_value="BRSSZ", entity=EntityRef(type="port", raw_name="Santos"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    ev3 = RichEvidence(evidence_id="ev_3", claim_field="terminal", claim_value="T39", entity=EntityRef(type="terminal", raw_name="T39"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    
    engine.apply_evidence(base_shipment, ev1)
    engine.apply_evidence(base_shipment, ev2)
    engine.apply_evidence(base_shipment, ev3)
    
    hyp = hypothesis_engine.evaluate_cargo(base_shipment)
    assert hyp is not None
    assert hyp.epistemic_state == EpistemicState.CONTRADICTION
    assert set(hyp.conflicting_evidence_ids) == {ev1.logical_id, ev2.logical_id, ev3.logical_id}

def test_hypothesis_does_not_alter_original_evidence(base_shipment, hypothesis_engine, engine):
    ev1 = RichEvidence(evidence_id="ev_1", claim_field="vessel.type", claim_value="bulk_carrier", entity=EntityRef(type="vessel", raw_name="A"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    ev2 = RichEvidence(evidence_id="ev_2", claim_field="port_call", claim_value="BRSSZ", entity=EntityRef(type="port", raw_name="Santos"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    ev3 = RichEvidence(evidence_id="ev_3", claim_field="terminal", claim_value="T39", entity=EntityRef(type="terminal", raw_name="T39"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    
    engine.apply_evidence(base_shipment, ev1)
    engine.apply_evidence(base_shipment, ev2)
    engine.apply_evidence(base_shipment, ev3)
    
    original_ev1_state = base_shipment.evidence_store[ev1.logical_id].epistemic_state
    
    hyp = hypothesis_engine.evaluate_cargo(base_shipment)
    hypothesis_engine.apply_hypothesis(base_shipment, hyp)
    
    assert base_shipment.evidence_store[ev1.logical_id].epistemic_state == original_ev1_state
    assert base_shipment.cargo.current_value == "soybeans"

def test_inferred_cannot_become_observed(base_shipment, hypothesis_engine):
    hyp = ShipmentHypothesis(
        hypothesis_id="hyp_invalid",
        claim_field="cargo",
        claim_value="iron_ore",
        epistemic_state=EpistemicState.OBSERVED,
        rationale="test",
        created_at="2026",
        provenance="engine"
    )
    with pytest.raises(ValueError, match="cannot declare an OBSERVED state"):
        hypothesis_engine.apply_hypothesis(base_shipment, hyp)

def test_idempotency(base_shipment, hypothesis_engine, engine):
    ev1 = RichEvidence(evidence_id="ev_1", claim_field="vessel.type", claim_value="bulk_carrier", entity=EntityRef(type="vessel", raw_name="A"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    ev2 = RichEvidence(evidence_id="ev_2", claim_field="port_call", claim_value="BRSSZ", entity=EntityRef(type="port", raw_name="Santos"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    ev3 = RichEvidence(evidence_id="ev_3", claim_field="terminal", claim_value="T39", entity=EntityRef(type="terminal", raw_name="T39"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    
    engine.apply_evidence(base_shipment, ev1)
    engine.apply_evidence(base_shipment, ev2)
    engine.apply_evidence(base_shipment, ev3)
    
    hyp1 = hypothesis_engine.evaluate_cargo(base_shipment)
    hypothesis_engine.apply_hypothesis(base_shipment, hyp1)
    
    hyp2 = hypothesis_engine.evaluate_cargo(base_shipment)
    hypothesis_engine.apply_hypothesis(base_shipment, hyp2)
    
    assert len(base_shipment.hypotheses) == 1

def test_hypothesis_is_reversible(base_shipment, hypothesis_engine, engine):
    ev1 = RichEvidence(evidence_id="ev_1", claim_field="vessel.type", claim_value="bulk_carrier", entity=EntityRef(type="vessel", raw_name="A"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    ev2 = RichEvidence(evidence_id="ev_2", claim_field="port_call", claim_value="BRSSZ", entity=EntityRef(type="port", raw_name="Santos"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    ev3 = RichEvidence(evidence_id="ev_3", claim_field="terminal", claim_value="T39", entity=EntityRef(type="terminal", raw_name="T39"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    
    engine.apply_evidence(base_shipment, ev1)
    engine.apply_evidence(base_shipment, ev2)
    engine.apply_evidence(base_shipment, ev3)
    
    hyp_before = hypothesis_engine.evaluate_cargo(base_shipment)
    assert hyp_before is not None
    
    del base_shipment.evidence_store[ev3.logical_id]
    
    hyp_after = hypothesis_engine.evaluate_cargo(base_shipment)
    assert hyp_after is None
