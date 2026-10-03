import uuid
from typing import Dict, List, Optional
from datetime import datetime, timezone

from src.reconstruction.models import (
    ShipmentReconstruction,
    ShipmentHypothesis,
    EpistemicState,
    RichEvidence
)

class HypothesisEngine:
    """
    Engine to generate controlled inferences (Hypotheses) based on collected evidence.
    Enforces epistemological invariants:
    - Never infers based on a single weak factor.
    - Prefer UNKNOWN (returns None) over weak inference.
    - INFERRED can never be converted to OBSERVED here.
    """

    def __init__(self, engine_version: str = "hypothesis_engine_v1"):
        self.engine_version = engine_version

    def evaluate_cargo(self, shipment: ShipmentReconstruction) -> Optional[ShipmentHypothesis]:
        """
        Evaluates the evidence store to deduce cargo.
        Rule for "soybeans" (INFERRED):
          - Vessel type must be 'bulk_carrier'
          - Port call must be 'BRSSZ'
          - Terminal must be 'T39' (or similar solid agribulk terminal)
          
        If Terminal contradicts Vessel Type (e.g. Tanker at T39), returns CONTRADICTION.
        If insufficient evidence, returns None (UNKNOWN).
        """
        evidence_store = shipment.evidence_store
        
        vessel_types = []
        port_calls = []
        terminals = []
        
        # Scan evidence
        for ev in evidence_store.values():
            if ev.claim_field == "vessel.type":
                vessel_types.append(ev)
            elif ev.claim_field == "port_call":
                port_calls.append(ev)
            elif ev.claim_field == "terminal":
                terminals.append(ev)
                
        # 1. No evidence -> UNKNOWN
        if not vessel_types and not port_calls and not terminals:
            return None
            
        # 2. Insufficient evidence -> UNKNOWN
        # We strictly require all three to make an INFERRED claim
        if not vessel_types or not port_calls or not terminals:
            return None
            
        # Analyze collected claims
        v_type_vals = [e.claim_value for e in vessel_types]
        port_vals = [e.claim_value for e in port_calls]
        term_vals = [e.claim_value for e in terminals]
        
        supporting_ids = []
        conflicting_ids = []
        
        # 4. Conflicting evidence check
        # e.g., Tanker at a dry bulk terminal
        is_tanker = any("tanker" in str(v).lower() for v in v_type_vals)
        is_dry_bulk = any("bulk_carrier" in str(v).lower() for v in v_type_vals)
        is_agri_terminal = any("T39" in str(t) for t in term_vals)
        
        supporting_ids.extend([e.logical_id for e in vessel_types + port_calls + terminals])
        
        if is_tanker and is_agri_terminal:
            # Conflicting! Tanker shouldn't be loading Soybeans at T39.
            return ShipmentHypothesis(
                hypothesis_id=f"hyp_{uuid.uuid4().hex[:8]}",
                claim_field="cargo",
                claim_value="soybeans",
                epistemic_state=EpistemicState.CONTRADICTION,
                supporting_evidence_ids=[],
                conflicting_evidence_ids=supporting_ids,
                rationale="Vessel type 'tanker' contradicts agricultural terminal profile.",
                confidence=0.0,
                created_at=datetime.now(timezone.utc).isoformat(),
                provenance=self.engine_version
            )
            
        # 3. Converging evidence -> INFERRED
        if is_dry_bulk and "BRSSZ" in port_vals and is_agri_terminal:
            return ShipmentHypothesis(
                hypothesis_id=f"hyp_{uuid.uuid4().hex[:8]}",
                claim_field="cargo",
                claim_value="soybeans",
                epistemic_state=EpistemicState.INFERRED, # Never OBSERVED
                supporting_evidence_ids=supporting_ids,
                conflicting_evidence_ids=[],
                rationale="Vessel is a bulk carrier calling an agricultural export terminal (T39) in Santos (BRSSZ).",
                confidence=0.85,
                created_at=datetime.now(timezone.utc).isoformat(),
                provenance=self.engine_version
            )
            
        # Fallback for insufficient combinations
        return None

    def apply_hypothesis(self, shipment: ShipmentReconstruction, hypothesis: ShipmentHypothesis) -> ShipmentReconstruction:
        """
        Applies a valid hypothesis to the shipment reconstruction if no better epistemic state exists.
        """
        if not hypothesis:
            return shipment
            
        # Idempotency check: if a hypothesis with same rationale/claims exists, skip
        for existing in shipment.hypotheses.values():
            if (existing.claim_field == hypothesis.claim_field and 
                existing.claim_value == hypothesis.claim_value and 
                set(existing.supporting_evidence_ids) == set(hypothesis.supporting_evidence_ids)):
                return shipment
                
        shipment.hypotheses[hypothesis.hypothesis_id] = hypothesis
        
        field = getattr(shipment, hypothesis.claim_field, None)
        if field is not None:
            # 6. INFERRED cannot become OBSERVED
            if hypothesis.epistemic_state == EpistemicState.OBSERVED:
                raise ValueError("A hypothesis cannot declare an OBSERVED state.")
                
            # Only apply if current state is weaker (e.g. UNKNOWN)
            # For simplicity, if current is UNKNOWN, apply it.
            if field.state == EpistemicState.UNKNOWN or field.state == EpistemicState.CONTRADICTION:
                field.current_value = hypothesis.claim_value
                field.state = hypothesis.epistemic_state
                field.supporting_evidence_ids = hypothesis.supporting_evidence_ids
                field.conflicting_evidence_ids = hypothesis.conflicting_evidence_ids
                
        return shipment
