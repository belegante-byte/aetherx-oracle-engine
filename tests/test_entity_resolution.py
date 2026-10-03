import pytest
from src.reconstruction.resolver import EntityResolver
from src.reconstruction.models import IdentityState, EpistemicState, ShipmentReconstruction

def test_vessel_with_explicit_imo():
    obs = {
        "imo": "9123456",
        "vessel_name": "VALE BRASIL",
        "port_id": "BRSSZ",
        "source": "santos_scraper",
        "ingested_at": "2026-10-02T10:00:00Z"
    }
    
    vessel, port_call, evidences = EntityResolver.resolve_vessel(obs, origin_order_id="ord_1")
    
    assert vessel.identity_state == IdentityState.OBSERVED
    assert vessel.imo == "9123456"
    assert vessel.name == "VALE BRASIL"
    assert len(vessel.evidence_ids) == 2
    
    assert port_call.port == "BRSSZ"
    assert port_call.vessel_id == "9123456"
    
    # Check provenance
    assert all(e.source == "santos_scraper" for e in evidences)
    assert all(e.origin_order_id == "ord_1" for e in evidences)
    assert all(e.retrieved_at == "2026-10-02T10:00:00Z" for e in evidences)

def test_vessel_name_only_and_normalization():
    # Also tests absence of IMO
    obs = {
        "imo": None,
        "vessel_name": " Msc  aLiCia ",
        "port_id": "BRSSZ",
        "source": "santos_scraper"
    }
    
    vessel, port_call, evidences = EntityResolver.resolve_vessel(obs)
    
    # Normalization removes extra spaces, capitalizes
    assert vessel.name == "MSC ALICIA"
    assert vessel.imo is None
    
    # Candidate not promoted to OBSERVED
    assert vessel.identity_state == IdentityState.CANDIDATE
    
    # Raw value preserved in evidence
    name_ev = next(e for e in evidences if e.claim_field == "vessel.name")
    assert name_ev.claim_value["raw_value"] == " Msc  aLiCia "
    assert name_ev.claim_value["normalized_value"] == "MSC ALICIA"

def test_imo_conflict():
    # Simulating a conflict between name and IMO by pushing a conflict marker,
    # or by resolving two conflicting observations for the same name in the Engine.
    # We will test the resolver's ability to mark CONTRADICTION if passed CONFLICT.
    obs = {
        "imo": "CONFLICT",
        "vessel_name": "VALE BRASIL",
        "port_id": "BRSSZ"
    }
    
    vessel, port_call, evidences = EntityResolver.resolve_vessel(obs)
    assert vessel.identity_state == IdentityState.CONTRADICTION

def test_same_observation_twice_idempotency():
    obs = {
        "imo": "9123456",
        "vessel_name": "VALE BRASIL",
        "port_id": "BRSSZ",
        "source": "santos_scraper"
    }
    
    vessel1, pc1, evs1 = EntityResolver.resolve_vessel(obs)
    vessel2, pc2, evs2 = EntityResolver.resolve_vessel(obs)
    
    # If passed to engine, duplicate evidences wouldn't affect the store size
    shipment = ShipmentReconstruction(shipment_id="shp_1")
    from src.reconstruction.engine import ReconstructionEngine
    engine = ReconstructionEngine()
    
    for ev in evs1:
        engine.apply_evidence(shipment, ev)
    
    initial_store_size = len(shipment.evidence_store)
    
    for ev in evs1: # Applying exactly the SAME evidence objects (same IDs)
        engine.apply_evidence(shipment, ev)
        
    assert len(shipment.evidence_store) == initial_store_size

def test_shipment_reconstruction_partial():
    obs = {
        "imo": "9123456",
        "vessel_name": "VALE BRASIL",
        "port_id": "BRSSZ"
    }
    
    vessel, port_call, evidences = EntityResolver.resolve_vessel(obs)
    
    shipment = ShipmentReconstruction(shipment_id="shp_1")
    
    # Manually mapping the resolved entities to the shipment to prove structure
    shipment.vessel.current_value = vessel
    shipment.vessel.state = EpistemicState.OBSERVED
    
    shipment.port_call.current_value = port_call
    shipment.port_call.state = EpistemicState.OBSERVED
    
    shipment.origin_port.current_value = port_call.port
    shipment.origin_port.state = EpistemicState.OBSERVED
    
    assert shipment.vessel.current_value.name == "VALE BRASIL"
    assert shipment.origin_port.current_value == "BRSSZ"
    
    # Fields remaining UNKNOWN
    assert shipment.cargo.state == EpistemicState.UNKNOWN
    assert shipment.shipper.state == EpistemicState.UNKNOWN
    assert shipment.consignee.state == EpistemicState.UNKNOWN
    assert shipment.destination_port.state == EpistemicState.UNKNOWN
