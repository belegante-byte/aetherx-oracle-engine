import pytest
from src.reconstruction.models import ShipmentReconstruction, PortCall, RichEvidence, EntityRef, EpistemicState
from src.reconstruction.engine import ReconstructionEngine

def test_shipment_identity_separation():
    # B. IDENTIDADE: Provar P != S1, P != S2, S1 != S2
    pc = PortCall(port="BRSSZ", vessel_id="urn:vessel:imo:1234567")
    
    # S1 and S2 map to distinct logical commercial shipments
    s1 = ShipmentReconstruction(shipment_id=f"{pc.stable_id}_bl_1")
    s2 = ShipmentReconstruction(shipment_id=f"{pc.stable_id}_bl_2")
    
    assert pc.stable_id != s1.stable_id
    assert pc.stable_id != s2.stable_id
    assert s1.stable_id != s2.stable_id
    
    # G. SEPARAR Operational Aggregator
    # The provisional fallback identity is clearly marked and isolated
    provisional_aggregator = ShipmentReconstruction(shipment_id=pc.stable_id)
    assert provisional_aggregator.stable_id == f"urn:shipment:{pc.stable_id}"

def test_multi_shipment_enrichment_without_collision():
    # C & D. CENÁRIO DE TESTE & ENRIQUECIMENTO
    engine = ReconstructionEngine()
    s1 = ShipmentReconstruction(shipment_id="S1_AGRI")
    s2 = ShipmentReconstruction(shipment_id="S2_MINERAL")
    
    # Base queries (Evidence A1 & B1)
    ev_a1 = RichEvidence(
        evidence_id="ev_a1", claim_field="cargo", claim_value="agricultural_bulk", 
        entity=EntityRef(type="shipment", raw_name="S1_AGRI"), 
        epistemic_state=EpistemicState.OBSERVED, source="terminal", retrieved_at="2026"
    )
    ev_b1 = RichEvidence(
        evidence_id="ev_b1", claim_field="cargo", claim_value="mineral_bulk", 
        entity=EntityRef(type="shipment", raw_name="S2_MINERAL"), 
        epistemic_state=EpistemicState.OBSERVED, source="terminal", retrieved_at="2026"
    )
    
    engine.apply_evidence(s1, ev_a1)
    engine.apply_evidence(s2, ev_b1)
    
    # Enrichment (Evidence A2 & B2)
    ev_a2 = RichEvidence(
        evidence_id="ev_a2", claim_field="destination_port", claim_value="X", 
        entity=EntityRef(type="shipment", raw_name="S1_AGRI"), 
        epistemic_state=EpistemicState.OBSERVED, source="terminal", retrieved_at="2026"
    )
    ev_b2 = RichEvidence(
        evidence_id="ev_b2", claim_field="destination_port", claim_value="Y", 
        entity=EntityRef(type="shipment", raw_name="S2_MINERAL"), 
        epistemic_state=EpistemicState.OBSERVED, source="terminal", retrieved_at="2026"
    )
    
    engine.apply_evidence(s1, ev_a2)
    engine.apply_evidence(s2, ev_b2)
    
    # Assert Coexistence and Independence
    assert s1.cargo.current_value == "agricultural_bulk"
    assert s1.destination_port.current_value == "X"
    
    assert s2.cargo.current_value == "mineral_bulk"
    assert s2.destination_port.current_value == "Y"
    
    # Ensure no cross contamination in transverse stores
    assert ev_b1.logical_id not in s1.evidence_store
    assert ev_a1.logical_id not in s2.evidence_store

def test_conflict_no_silent_overwrite():
    # E. CONFLITO
    engine = ReconstructionEngine()
    s = ShipmentReconstruction(shipment_id="S_conflict")
    
    ev_initial = RichEvidence(
        evidence_id="e1", claim_field="cargo", claim_value="agricultural_bulk", 
        entity=EntityRef(type="shipment", raw_name="S_conflict"), 
        epistemic_state=EpistemicState.OBSERVED, source="A", retrieved_at="2026"
    )
    ev_conflict = RichEvidence(
        evidence_id="e2", claim_field="cargo", claim_value="mineral_bulk", 
        entity=EntityRef(type="shipment", raw_name="S_conflict"), 
        epistemic_state=EpistemicState.OBSERVED, source="B", retrieved_at="2026"
    )
    
    engine.apply_evidence(s, ev_initial)
    engine.apply_evidence(s, ev_conflict)
    
    # Do not silently overwrite previous value!
    assert s.cargo.state == EpistemicState.CONTRADICTION
    # Both evidences must be explicitly tracked in the conflict ledger
    assert (ev_initial.logical_id in s.cargo.supporting_evidence_ids) or (ev_initial.logical_id in s.cargo.conflicting_evidence_ids)
    assert (ev_conflict.logical_id in s.cargo.supporting_evidence_ids) or (ev_conflict.logical_id in s.cargo.conflicting_evidence_ids)

def test_insufficient_identity():
    # F. IDENTIDADE INSUFICIENTE
    # Simulates the conceptual identity resolver for Phase 4B/Phase 5
    def resolve_shipment_identity(vessel, portcall, cargo=None, dest=None, consignee=None):
        if consignee:
            return f"shp_{portcall}_{consignee}", "IDENTIFIED"
        if cargo and dest:
            return f"shp_cand_{portcall}_{cargo}_{dest}", "CANDIDATE"
        # Otherwise fallback to PROVISIONAL OPERATIONAL AGGREGATOR
        return f"{portcall}", "PROVISIONAL"
        
    # 1. apenas vessel + portcall
    id1, state1 = resolve_shipment_identity("V1", "P1")
    assert state1 == "PROVISIONAL"
    
    # 2. vessel + portcall + cargo
    id2, state2 = resolve_shipment_identity("V1", "P1", cargo="agri")
    assert state2 == "PROVISIONAL" # Cargo alone on a portcall is NOT a shipment ID
    
    # 3. vessel + portcall + destination
    id3, state3 = resolve_shipment_identity("V1", "P1", dest="X")
    assert state3 == "PROVISIONAL"
    
    # 4. vessel + portcall + cargo + destination
    id4, state4 = resolve_shipment_identity("V1", "P1", cargo="agri", dest="X")
    assert state4 == "CANDIDATE" # Partial uniqueness reached
    
    # 5. vessel + portcall + consignee
    id5, state5 = resolve_shipment_identity("V1", "P1", consignee="AGRI_CORP")
    assert state5 == "IDENTIFIED" # Highly specific identifier establishes strong identity
