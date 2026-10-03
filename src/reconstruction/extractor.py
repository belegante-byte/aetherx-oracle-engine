import uuid
from typing import Dict, Any, List
from datetime import datetime, timezone

from src.reconstruction.models import (
    RichEvidence,
    EpistemicState,
    OperationalOrder,
    EntityRef
)

class OrderExtractor:
    @staticmethod
    def extract_from_assess_logistics(order: OperationalOrder, raw_result: Dict[str, Any]) -> List[RichEvidence]:
        """
        Translates assess_logistics_disruption output into RichEvidence.
        Does NOT invent missing data.
        """
        evidences = []
        
        # 1. Subject extraction (BRSSZ)
        subject = raw_result.get("subject", {})
        port_id = subject.get("port_id")
        
        if not port_id:
            return evidences
            
        port_entity = EntityRef(type="port", id=port_id, raw_name=port_id)
        
        # Determine retrieved timestamp from payload if possible
        retrieved_at = raw_result.get("generated_at", order.issued_at)
        
        # Extract the fact that this port is part of the operational order
        evidences.append(
            RichEvidence(
                evidence_id=f"ev_{uuid.uuid4().hex[:8]}",
                claim_field="origin_port",
                claim_value=port_id,
                entity=port_entity,
                epistemic_state=EpistemicState.OBSERVED,
                confidence=1.0,
                source="operational_order",
                source_observed_at=retrieved_at,
                retrieved_at=retrieved_at,
                origin_order_id=order.order_id
            )
        )
        
        # 2. Data Quality & Provenance
        dq = raw_result.get("data_quality", {})
        prov_list = raw_result.get("provenance", [])
        
        # Look for the primary port_risk observation in provenance
        port_prov = next((p for p in prov_list if p.get("tool") == "calculate_port_risk"), {})
        
        source = port_prov.get("source", dq.get("source", "unknown"))
        source_observed_at = port_prov.get("observed_at", dq.get("source_observed_at"))
        retrieved_at = raw_result.get("generated_at", datetime.now(timezone.utc).isoformat())
        
        # Epistemological assignment based on AETHER-X classifications
        classification = dq.get("classification", "unknown")
        
        if classification in ["live_verified", "live_stale", "live_unverified_time"]:
            epistemic_state = EpistemicState.OBSERVED
        elif classification == "reference":
            epistemic_state = EpistemicState.ESTIMATED
        else:
            epistemic_state = EpistemicState.DERIVED
            
        # 3. Observations Extraction
        observations = raw_result.get("observations", [])
        
        for obs in observations:
            fact = obs.get("fact", "")
            if "status:" in fact and "Delayed:" in fact:
                evidences.append(
                    RichEvidence(
                        evidence_id=f"ev_{uuid.uuid4().hex[:8]}",
                        claim_field="status",
                        claim_value=fact,
                        entity=port_entity,
                        epistemic_state=epistemic_state,
                        confidence=1.0 if epistemic_state == EpistemicState.OBSERVED else 0.8,
                        source=source,
                        source_observed_at=source_observed_at,
                        retrieved_at=retrieved_at,
                        origin_order_id=order.order_id
                    )
                )
                
        return evidences
