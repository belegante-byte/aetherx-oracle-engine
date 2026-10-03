from typing import Dict, List, Any
from src.reconstruction.models import ShipmentReconstruction, RichEvidence, EpistemicState

class ReconstructionEngine:
    """
    Motor base para absorver evidências e atualizar o ShipmentReconstruction.
    Garante os invariantes epistemológicos.
    """
    
    @staticmethod
    def apply_evidence(shipment: ShipmentReconstruction, evidence: RichEvidence) -> ShipmentReconstruction:
        """
        Aplica uma nova evidência ao embarque, atualizando o campo correspondente
        caso a nova evidência seja 'melhor' epistemicamente ou detectando contradição.
        """
        # Idempotência lógica
        lid = evidence.logical_id
        if lid in shipment.evidence_store:
            return shipment
            
        shipment.evidence_store[lid] = evidence
        field_name = evidence.claim_field
        
        # Obter o campo correspondente no modelo
        if not hasattr(shipment, field_name):
            return shipment # Ignora campos não mapeados no modelo principal por enquanto
            
        field = getattr(shipment, field_name)
        
        # Lógica de escada epistêmica (simplificada para o MVP)
        state_ranks = {
            EpistemicState.OBSERVED: 6,
            EpistemicState.DERIVED: 5,
            EpistemicState.ESTIMATED: 4,
            EpistemicState.INFERRED: 3,
            EpistemicState.HYPOTHESIS: 2,
            EpistemicState.UNKNOWN: 1,
            EpistemicState.CONTRADICTION: 0
        }
        
        current_rank = state_ranks.get(field.state, 1)
        new_rank = state_ranks.get(evidence.epistemic_state, 1)
        
        if field.state == EpistemicState.UNKNOWN:
            # Primeiro valor
            field.current_value = evidence.claim_value
            field.state = evidence.epistemic_state
            field.supporting_evidence_ids.append(lid)
        elif current_rank == new_rank and field.current_value != evidence.claim_value:
            # Contradição do mesmo nível epistêmico
            field.state = EpistemicState.CONTRADICTION
            field.conflicting_evidence_ids.append(lid)
        elif new_rank > current_rank:
            # Upgrade epistêmico
            field.current_value = evidence.claim_value
            field.state = evidence.epistemic_state
            # A evidência anterior vira 'suporte' ou é apenas superada (simplificamos aqui)
            field.supporting_evidence_ids = [lid]
        else:
            # Downgrade ou suporte adicional (não altera o valor atual)
            if field.current_value == evidence.claim_value:
                field.supporting_evidence_ids.append(lid)
            else:
                field.conflicting_evidence_ids.append(lid)
                
        return shipment
