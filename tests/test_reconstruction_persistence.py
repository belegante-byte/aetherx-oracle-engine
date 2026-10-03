import pytest
import duckdb
from src.reconstruction.models import RichEvidence, ShipmentReconstruction, VesselEntity, PortCall, EntityRef, EpistemicState, IdentityState
from src.reconstruction.persistence.repository import ReconstructionRepository
from src.reconstruction.engine import ReconstructionEngine

@pytest.fixture
def repo():
    # DISPOSABLE DUCKDB
    conn = duckdb.connect(":memory:")
    yield ReconstructionRepository(conn)
    conn.close()

def test_evidence_ledger_append_only_dedup(repo):
    # B. EVIDENCE LEDGER & J. IDEMPOTENCY
    ev = RichEvidence(
        evidence_id="e1", claim_field="cargo", claim_value="SOJA",
        entity=EntityRef(type="shipment", raw_name="S1"),
        epistemic_state=EpistemicState.OBSERVED, source="AIS", retrieved_at="2026"
    )
    res1 = repo.save_evidence(ev)
    assert res1 == "INSERTED"
    
    # Second insertion
    res2 = repo.save_evidence(ev)
    assert res2 == "DEDUPLICATED"
    
    # Ensure only 1 row exists
    count = repo.conn.execute("SELECT count(*) FROM evidence_ledger").fetchone()[0]
    assert count == 1

def test_source_independence(repo):
    # C. SOURCE INDEPENDENCE
    evA = RichEvidence(
        evidence_id="eA", claim_field="cargo", claim_value="SOJA",
        entity=EntityRef(type="shipment", raw_name="S1"),
        epistemic_state=EpistemicState.OBSERVED, source="SourceA", retrieved_at="2026"
    )
    evB = RichEvidence(
        evidence_id="eB", claim_field="cargo", claim_value="SOJA",
        entity=EntityRef(type="shipment", raw_name="S1"),
        epistemic_state=EpistemicState.OBSERVED, source="SourceB", retrieved_at="2026"
    )
    
    repo.save_evidence(evA)
    repo.save_evidence(evB)
    
    # Must NOT deduplicate
    count = repo.conn.execute("SELECT count(*) FROM evidence_ledger").fetchone()[0]
    assert count == 2

def test_shipment_persistence_and_restart():
    # D & E. SHIPMENT & PROCESS RESTART & L. SERIALIZATION
    db_path = "test_disposable_restart.duckdb"
    
    # Process 1
    conn1 = duckdb.connect(db_path)
    repo1 = ReconstructionRepository(conn1)
    
    v = VesselEntity(identity_state=IdentityState.OBSERVED, imo="111")
    pc = PortCall(port="BRSSZ", vessel_id=v.stable_id)
    s = ShipmentReconstruction(shipment_id="S_TEST")
    s.port_call.current_value = pc.stable_id
    
    ev = RichEvidence(
        evidence_id="e1", claim_field="cargo", claim_value="SOJA",
        entity=EntityRef(type="shipment", raw_name="S_TEST"),
        epistemic_state=EpistemicState.OBSERVED, source="AIS", retrieved_at="2026"
    )
    
    engine = ReconstructionEngine()
    engine.apply_evidence(s, ev)
    
    repo1.save_evidence(ev)
    repo1.save_vessel(v)
    repo1.save_port_call(pc)
    repo1.save_shipment(s)
    conn1.close()
    
    # Process 2
    conn2 = duckdb.connect(db_path)
    repo2 = ReconstructionRepository(conn2)
    
    loaded_s = repo2.load_shipment("urn:shipment:S_TEST")
    assert loaded_s is not None
    assert loaded_s.cargo.current_value == "SOJA"
    assert loaded_s.cargo.state == EpistemicState.OBSERVED
    assert ev.logical_id in loaded_s.evidence_store
    
    conn2.close()
    
    # cleanup
    import os
    if os.path.exists(db_path):
        os.remove(db_path)

def test_replay_from_ledger(repo):
    # F. REPLAY
    ev1 = RichEvidence(
        evidence_id="e1", claim_field="cargo", claim_value="SOJA",
        entity=EntityRef(type="shipment", raw_name="S_REPLAY"),
        epistemic_state=EpistemicState.OBSERVED, source="A", retrieved_at="2026"
    )
    ev2 = RichEvidence(
        evidence_id="e2", claim_field="destination_port", claim_value="CNTAO",
        entity=EntityRef(type="shipment", raw_name="S_REPLAY"),
        epistemic_state=EpistemicState.OBSERVED, source="A", retrieved_at="2026"
    )
    repo.save_evidence(ev1)
    repo.save_evidence(ev2)
    
    # Replay
    active_evidences = repo.get_active_evidence_for_entity("S_REPLAY")
    assert len(active_evidences) == 2
    
    s = ShipmentReconstruction(shipment_id="S_REPLAY")
    engine = ReconstructionEngine()
    for e in active_evidences:
        engine.apply_evidence(s, e)
        
    assert s.cargo.current_value == "SOJA"
    assert s.destination_port.current_value == "CNTAO"

def test_tombstone_retraction(repo):
    # G. TOMBSTONE / RETRACTION
    ev1 = RichEvidence(
        evidence_id="e1", claim_field="cargo", claim_value="SOJA",
        entity=EntityRef(type="shipment", raw_name="S_TOMB"),
        epistemic_state=EpistemicState.OBSERVED, source="A", retrieved_at="2026"
    )
    repo.save_evidence(ev1)
    
    # Insert tombstone
    repo.mark_tombstone(ev1.logical_id, "2026-10-02T12:00:00Z")
    
    # Must NOT physically delete the row!
    count = repo.conn.execute("SELECT count(*) FROM evidence_ledger").fetchone()[0]
    assert count == 2 # 1 evidence + 1 tombstone
    
    # But active retrieval should ignore it
    active = repo.get_active_evidence_for_entity("S_TOMB")
    assert len(active) == 0

def test_contradiction(repo):
    # H. CONTRADICTION
    evA = RichEvidence(
        evidence_id="eA", claim_field="cargo", claim_value="SOJA",
        entity=EntityRef(type="shipment", raw_name="S_CONF"),
        epistemic_state=EpistemicState.OBSERVED, source="A", retrieved_at="2026"
    )
    evB = RichEvidence(
        evidence_id="eB", claim_field="cargo", claim_value="MILHO",
        entity=EntityRef(type="shipment", raw_name="S_CONF"),
        epistemic_state=EpistemicState.OBSERVED, source="B", retrieved_at="2026"
    )
    repo.save_evidence(evA)
    repo.save_evidence(evB)
    
    active = repo.get_active_evidence_for_entity("S_CONF")
    s = ShipmentReconstruction(shipment_id="S_CONF")
    engine = ReconstructionEngine()
    for e in active:
        engine.apply_evidence(s, e)
        
    assert s.cargo.state == EpistemicState.CONTRADICTION
    # Both evidences persisted
    assert len(active) == 2

def test_multi_shipment_no_cross_contamination(repo):
    # I. MULTI-SHIPMENT
    s1 = ShipmentReconstruction(shipment_id="S1")
    s1.destination_port.current_value = "X"
    s1.destination_port.state = EpistemicState.OBSERVED
    
    s2 = ShipmentReconstruction(shipment_id="S2")
    s2.destination_port.current_value = "Y"
    s2.destination_port.state = EpistemicState.OBSERVED
    
    repo.save_shipment(s1)
    repo.save_shipment(s2)
    
    # Read back
    ls1 = repo.load_shipment(s1.stable_id)
    ls2 = repo.load_shipment(s2.stable_id)
    
    assert ls1.destination_port.current_value == "X"
    assert ls2.destination_port.current_value == "Y"

def test_atomicity_rollback(repo):
    # K. ATOMICITY
    repo.begin_transaction()
    s = ShipmentReconstruction(shipment_id="S_FAIL")
    repo.save_shipment(s)
    repo.rollback_transaction()
    
    assert repo.load_shipment(s.stable_id) is None
