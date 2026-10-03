import pytest
import os
import subprocess
from unittest import mock

from src.api.mcp_app import assess_logistics_disruption
from src.reconstruction.shadow_store import shadow_store
from src.reconstruction.models import ShipmentHypothesis, EpistemicState

@pytest.fixture(autouse=True)
def reset_shadow_store_fixture():
    shadow_store.reset_state()

def test_shadow_pipeline_basic():
    res = assess_logistics_disruption("BRSSZ", objective="demurrage_avoidance")
    assert res["status"] in ["complete", "partial", "insufficient_data"]
    
    metrics = shadow_store.get_metrics()
    assert metrics["orders_processed"] == 1
    assert metrics["new_evidence"] > 0
    assert metrics["new_entities"] > 0

def test_mcp_response_isolation_on_total_failure():
    # A. MCP response isolation
    # Simular falha total do reconstruction pipeline (e.g. ValueError na raiz)
    with mock.patch("src.reconstruction.shadow_pipeline.run_shadow_pipeline", side_effect=ValueError("Simulated shadow fail")):
        res = assess_logistics_disruption("BRSSZ", objective="demurrage_avoidance")
        # Deve retornar sucesso normal
        assert res["status"] in ["complete", "partial", "insufficient_data"]
        
def test_partial_failure():
    # C. Partial failure: extractor OK, resolver/engine FAIL
    with mock.patch("src.reconstruction.shadow_pipeline.ReconstructionEngine.apply_evidence", side_effect=Exception("Partial")):
        res = assess_logistics_disruption("BRSSZ", objective="demurrage_avoidance")
        assert res["status"] in ["complete", "partial", "insufficient_data"]
        metrics = shadow_store.get_metrics()
        assert metrics["orders_processed"] == 1
        assert metrics["pipeline_failures"] == 1

def test_idempotency_shadow_integration():
    # B. Idempotência
    res1 = assess_logistics_disruption("BRSSZ", objective="demurrage_avoidance")
    m1 = shadow_store.get_metrics()
    
    # Store state to mock exact same payload for the second call to force idempotency correctly 
    # (since assess_logistics_disruption might change 'generated_at' timestamp)
    with mock.patch("src.api.mcp_app._run_tool") as mock_tool:
        # Just manually pass the same dict to the shadow pipeline directly
        from src.reconstruction.shadow_pipeline import run_shadow_pipeline
        run_shadow_pipeline("BRSSZ", "demurrage_avoidance", res1)
        
    m2 = shadow_store.get_metrics()
    assert m2["orders_processed"] == 2
    assert m2["deduplicated_evidence"] > 0 # Duplicates were detected
    assert m2["new_evidence"] == m1["new_evidence"] # No new evidence was created!

def test_hypothesis_isolation():
    # D. Hypothesis isolation
    # Hypothesis Engine does not mutate the evidence_store itself.
    from src.reconstruction.models import ShipmentReconstruction, RichEvidence, EntityRef
    from src.reconstruction.hypothesis_engine import HypothesisEngine
    
    shipment = ShipmentReconstruction(shipment_id="shp_test")
    ev1 = RichEvidence(evidence_id="ev_1", claim_field="vessel.type", claim_value="bulk_carrier", entity=EntityRef(type="vessel", raw_name="A"), epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026")
    shipment.evidence_store[ev1.logical_id] = ev1
    
    h_engine = HypothesisEngine()
    invalid_hyp = ShipmentHypothesis(
        hypothesis_id="hyp_inv", claim_field="cargo", claim_value="soybeans",
        epistemic_state=EpistemicState.OBSERVED, # invalid state
        rationale="test", created_at="2026", provenance="test"
    )
    
    with pytest.raises(ValueError):
        h_engine.apply_hypothesis(shipment, invalid_hyp)
        
    # Evidence remains intact
    assert shipment.evidence_store[ev1.logical_id].epistemic_state == EpistemicState.OBSERVED
    
def test_temporal_integrity():
    # E. Temporal integrity
    from src.reconstruction.models import OperationalOrder
    from src.reconstruction.extractor import OrderExtractor
    
    order = OperationalOrder(order_id="1", consumer="1", issued_at="2026", objective="1", parameters={})
    mock_payload = {
        "subject": {"port_id": "BRSSZ"},
        "generated_at": "2026-10-02T10:00:00Z",
        "data_quality": {"source_observed_at": None, "retrieved_at": "2026-10-02T10:00:00Z"},
        "observations": [{"fact": "Test", "source": "test"}]
    }
    evs = OrderExtractor.extract_from_assess_logistics(order, mock_payload)
    for ev in evs:
        # source_observed_at must NOT be faked with retrieved_at
        if ev.claim_field != "origin_port": # origin_port copies issued_at as it's the target itself
            assert ev.source_observed_at is None

def test_production_db_protection():
    # F. Production DB protection
    # AETHER-X sandbox test
    import duckdb
    # Try to open the DB exclusively for write - this would fail if someone holds it,
    # but more importantly, we assert shadow store is NOT pointing to it.
    assert os.getenv("SHADOW_DB_PATH", ":memory:") != "data/oracle.duckdb"
    
    # Check that oracle wasn't modified
    result = subprocess.run(
        ["git", "diff", "--name-only", "data/oracle.duckdb"],
        cwd="/Users/AETHER - X",
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "", "Oracle database mutated!"
