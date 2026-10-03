import pytest
from src.reconstruction.models import (
    VesselEntity, PortCall, Voyage, ShipmentReconstruction, IdentityState,
    RichEvidence, EntityRef, EpistemicState
)
from src.reconstruction.engine import ReconstructionEngine

def test_cardinality_one_portcall_multiple_shipments():
    # Demonstrating the domain can represent 1 Vessel -> 1 PortCall -> 2 Shipments
    # without collapsing them.
    vessel = VesselEntity(identity_state=IdentityState.OBSERVED, imo="1234567")
    port_call = PortCall(port="BRSSZ", vessel_id=vessel.stable_id)
    
    # Shipment 1 (e.g. Soybeans for Shipper A)
    shipment_1 = ShipmentReconstruction(shipment_id=f"shp_{port_call.stable_id}_bl_001")
    # Shipment 2 (e.g. Corn for Shipper B)
    shipment_2 = ShipmentReconstruction(shipment_id=f"shp_{port_call.stable_id}_bl_002")
    
    # Both reference the same port call natively
    assert shipment_1.stable_id != shipment_2.stable_id
    assert port_call.stable_id in shipment_1.stable_id
    assert port_call.stable_id in shipment_2.stable_id

def test_cardinality_one_voyage_multiple_portcalls():
    # Demonstrating the domain can represent 1 Voyage -> N PortCalls
    vessel = VesselEntity(identity_state=IdentityState.OBSERVED, imo="1234567")
    
    pc_1 = PortCall(port="BRPNG", vessel_id=vessel.stable_id)
    pc_2 = PortCall(port="BRSSZ", vessel_id=vessel.stable_id)
    pc_3 = PortCall(port="CNTAO", vessel_id=vessel.stable_id)
    
    voyage = Voyage(
        voyage_id=f"voy_{vessel.stable_id}_2026",
        vessel_id=vessel.stable_id,
        port_call_ids=[pc_1.stable_id, pc_2.stable_id, pc_3.stable_id]
    )
    
    assert len(voyage.port_call_ids) == 3
    assert pc_1.stable_id in voyage.port_call_ids
    assert pc_3.stable_id in voyage.port_call_ids

def test_semantic_enrichment_accumulation():
    # Testar enriquecimento semântico incremental
    engine = ReconstructionEngine()
    shipment = ShipmentReconstruction(shipment_id="shp_test_enrichment")
    
    # Query A -> Vessel + PortCall
    ev_vessel = RichEvidence(
        evidence_id="ev_1", claim_field="vessel", claim_value="IMO1234567",
        entity=EntityRef(type="vessel", raw_name="Test Vessel"),
        epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026"
    )
    ev_portcall = RichEvidence(
        evidence_id="ev_2", claim_field="port_call", claim_value="BRSSZ",
        entity=EntityRef(type="port", raw_name="Santos"),
        epistemic_state=EpistemicState.OBSERVED, source="ais", retrieved_at="2026"
    )
    engine.apply_evidence(shipment, ev_vessel)
    engine.apply_evidence(shipment, ev_portcall)
    
    # Query B -> Cargo
    ev_cargo = RichEvidence(
        evidence_id="ev_3", claim_field="cargo", claim_value="soybeans",
        entity=EntityRef(type="shipment", id="shp_test_enrichment", raw_name="shipment"),
        epistemic_state=EpistemicState.INFERRED, source="model", retrieved_at="2026"
    )
    engine.apply_evidence(shipment, ev_cargo)
    
    # Query C -> Destination
    ev_dest = RichEvidence(
        evidence_id="ev_4", claim_field="destination_port", claim_value="CNTAO",
        entity=EntityRef(type="shipment", id="shp_test_enrichment", raw_name="shipment"),
        epistemic_state=EpistemicState.OBSERVED, source="doc", retrieved_at="2026"
    )
    engine.apply_evidence(shipment, ev_dest)
    
    # Query D -> Shipper
    ev_shipper = RichEvidence(
        evidence_id="ev_5", claim_field="shipper", claim_value="AGRI_CORP",
        entity=EntityRef(type="shipment", id="shp_test_enrichment", raw_name="shipment"),
        epistemic_state=EpistemicState.DERIVED, source="commercial_db", retrieved_at="2026"
    )
    engine.apply_evidence(shipment, ev_shipper)
    
    # Esperado: Shipment Reconstruction S totalmente preenchido, sem perder evidências
    assert shipment.vessel.current_value == "IMO1234567"
    assert shipment.port_call.current_value == "BRSSZ"
    assert shipment.cargo.current_value == "soybeans"
    assert shipment.destination_port.current_value == "CNTAO"
    assert shipment.shipper.current_value == "AGRI_CORP"
    
    # As evidências transversais continuam no store sustentando os campos
    assert len(shipment.evidence_store) == 5
    assert ev_shipper.logical_id in shipment.shipper.supporting_evidence_ids
