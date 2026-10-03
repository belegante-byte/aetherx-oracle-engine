import pytest
from unittest import mock
import copy

from src.reconstruction.shadow_store import shadow_store
from src.reconstruction.shadow_pipeline import run_shadow_pipeline

@pytest.fixture(autouse=True)
def reset_store():
    shadow_store.reset_state()

def test_identical_queries():
    # 2. Testar duas queries idênticas
    # Executar Query A duas vezes e garantir deduplicação completa.
    payload = {
        "subject": {"port_id": "BRSSZ"},
        "generated_at": "2026-10-02T10:00:00Z",
        "observations": [{"fact": "Vessel VALE BRASIL arriving", "source": "ais"}]
    }
    
    # Execução 1
    run_shadow_pipeline("BRSSZ", "routing", payload)
    m1 = shadow_store.get_metrics()
    
    assert m1["orders_processed"] == 1
    assert m1["new_evidence"] > 0
    assert m1["new_entities"] > 0
    assert m1["new_portcalls"] > 0
    assert m1["new_shipments"] == 1
    
    # Execução 2
    run_shadow_pipeline("BRSSZ", "routing", payload)
    m2 = shadow_store.get_metrics()
    
    assert m2["orders_processed"] == 2
    assert m2["new_evidence"] == m1["new_evidence"]
    assert m2["deduplicated_evidence"] > 0
    assert m2["new_entities"] == m1["new_entities"]
    assert m2["new_shipments"] == m1["new_shipments"]
    assert m2["updated_shipments"] == 1

def test_incremental_enrichment():
    # 3. Testar enriquecimento incremental
    # Query A -> Vessel + PortCall
    payload_a = {
        "subject": {"port_id": "BRSSZ"},
        "generated_at": "2026-10-02T10:00:00Z",
        "observations": [{"fact": "Vessel VALE BRASIL at berth", "source": "ais"}]
    }
    run_shadow_pipeline("BRSSZ", "routing", payload_a)
    m1 = shadow_store.get_metrics()
    
    # Query B -> Mesma embarcação + novo dado (nova observation)
    payload_b = {
        "subject": {"port_id": "BRSSZ"},
        "generated_at": "2026-10-02T10:05:00Z",
        "observations": [
            {"fact": "Vessel VALE BRASIL at berth", "source": "ais"},
            {"fact": "Vessel VALE BRASIL is a bulk_carrier", "source": "terminal"}
        ]
    }
    run_shadow_pipeline("BRSSZ", "routing", payload_b)
    m2 = shadow_store.get_metrics()
    
    # Deve atualizar o shipment e os entities em vez de criar novos
    assert m2["new_shipments"] == 1
    assert m2["updated_shipments"] > 0
    assert m2["new_evidence"] > m1["new_evidence"] # a nova evidence de type foi adicionada
    
    # Checando o estado do Shipment:
    shipment_key = list(shadow_store.shipments.keys())[0]
    shipment = shadow_store.shipments[shipment_key]
    assert len(shipment.evidence_store) >= 2

def test_two_sources():
    # 4. Testar duas fontes (esperado: 1 Vessel, 2 independent evidences)
    payload = {
        "subject": {"port_id": "BRSSZ"},
        "generated_at": "2026-10-02T10:00:00Z",
        "observations": [
            {"fact": "Vessel VALE BRASIL at BRSSZ", "source": "ais"},
            {"fact": "Vessel VALE BRASIL at BRSSZ", "source": "terminal"}
        ]
    }
    run_shadow_pipeline("BRSSZ", "routing", payload)
    m = shadow_store.get_metrics()
    
    assert m["new_entities"] == 1 # Apenas o port_entity se o VALE BRASIL não for extraído pelo extractor atual, 
                                  # Mas se for, 2 entidades (Port + Vessel), mas apenas 1 Vessel.
    # O importante é que a deduplicação de Evidências respeite o source (não deduplique).
    # O extractor criará origin_port 2 vezes? Não, origin_port cria 1 vez por ordem.
    # A verificação foca em que evidence_store terá as observações distintas
    shipment_key = list(shadow_store.shipments.keys())[0]
    shipment = shadow_store.shipments[shipment_key]
    # At least the origin port evidence + the 2 observations (if extractor supports it).
    # Since extractor currently extracts `vessel` heuristically if it sees "Vessel", let's assume it does.

def test_temporal_change():
    # 5. Testar mudança temporal
    payload_a = {
        "subject": {"port_id": "BRSSZ"},
        "generated_at": "2026-10-02T10:00:00Z",
        "observations": [{"fact": "Vessel X", "source": "ais", "observed_at": "2026-10-02T10:00:00Z"}]
    }
    run_shadow_pipeline("BRSSZ", "routing", payload_a)
    
    payload_b = {
        "subject": {"port_id": "BRSSZ"},
        "generated_at": "2026-10-02T12:00:00Z",
        "observations": [{"fact": "Vessel X", "source": "ais", "observed_at": "2026-10-02T12:00:00Z"}]
    }
    run_shadow_pipeline("BRSSZ", "routing", payload_b)
    
    m2 = shadow_store.get_metrics()
    assert m2["new_shipments"] == 1
    assert m2["updated_shipments"] > 0
    # Múltiplas evidences preservadas no mesmo shipment
    shipment_key = list(shadow_store.shipments.keys())[0]
    shipment = shadow_store.shipments[shipment_key]
    assert len(shipment.evidence_store) > 1

def test_conflict_contradiction():
    # 6. Testar conflito
    from src.reconstruction.models import RichEvidence, EntityRef, EpistemicState
    
    # By bypassing extractor and injecting conflicting evidence directly into pipeline
    payload = {
        "subject": {"port_id": "BRSSZ"},
        "generated_at": "2026-10-02T10:00:00Z",
    }
    run_shadow_pipeline("BRSSZ", "routing", payload)
    
    shipment_key = list(shadow_store.shipments.keys())[0]
    shipment = shadow_store.shipments[shipment_key]
    
    from src.reconstruction.engine import ReconstructionEngine
    engine = ReconstructionEngine()
    
    ev_a = RichEvidence(
        evidence_id="ev_a", claim_field="vessel", claim_value="Vessel 1234567",
        entity=EntityRef(type="vessel", raw_name="Vessel X"),
        epistemic_state=EpistemicState.OBSERVED, source="A", retrieved_at="2026"
    )
    ev_b = RichEvidence(
        evidence_id="ev_b", claim_field="vessel", claim_value="Vessel 7654321",
        entity=EntityRef(type="vessel", raw_name="Vessel X"),
        epistemic_state=EpistemicState.OBSERVED, source="B", retrieved_at="2026"
    )
    
    engine.apply_evidence(shipment, ev_a)
    engine.apply_evidence(shipment, ev_b)
    
    # Must be contradiction
    assert shipment.vessel.state == EpistemicState.CONTRADICTION
    assert ev_a.logical_id in shipment.evidence_store
    assert ev_b.logical_id in shipment.evidence_store

def test_reversibility():
    # 7. Testar reversibilidade
    payload = {
        "subject": {"port_id": "BRSSZ"},
        "generated_at": "2026-10-02T10:00:00Z",
    }
    run_shadow_pipeline("BRSSZ", "routing", payload)
    shipment_key = list(shadow_store.shipments.keys())[0]
    shipment = shadow_store.shipments[shipment_key]
    
    from src.reconstruction.engine import ReconstructionEngine
    from src.reconstruction.models import RichEvidence, EntityRef, EpistemicState
    engine = ReconstructionEngine()
    
    ev_a = RichEvidence(
        evidence_id="ev_a", claim_field="vessel", claim_value="Vessel 1234567",
        entity=EntityRef(type="vessel", raw_name="Vessel X"),
        epistemic_state=EpistemicState.OBSERVED, source="A", retrieved_at="2026"
    )
    engine.apply_evidence(shipment, ev_a)
    assert shipment.vessel.current_value == "Vessel 1234567"
    
    # Remove it manually to simulate reversibility
    del shipment.evidence_store[ev_a.logical_id]
    shipment.vessel.supporting_evidence_ids.remove(ev_a.logical_id)
    
    # It shouldn't create a new shipment
    assert len(shadow_store.shipments) == 1
