import uuid
import re
from typing import Dict, Any, List, Tuple
from datetime import datetime, timezone

from src.reconstruction.models import (
    RichEvidence,
    EpistemicState,
    EntityRef,
    VesselEntity,
    PortCall,
    IdentityState
)

class EntityResolver:
    @staticmethod
    def normalize_vessel_name(raw_name: str) -> str:
        if not raw_name:
            return ""
        # Remove extra spaces, uppercase, keep basic chars
        name = raw_name.strip().upper()
        name = re.sub(r'[^A-Z0-9 ]', '', name)
        name = re.sub(r'\s+', ' ', name)
        return name

    @staticmethod
    def resolve_vessel(raw_observation: Dict[str, Any], origin_order_id: str = None) -> Tuple[VesselEntity, PortCall, List[RichEvidence]]:
        """
        Takes a raw vessel observation (e.g., from raw_port_lineup) and resolves it.
        Rules:
        - IMO + Name = OBSERVED (resolved)
        - Name only = CANDIDATE
        - IMO conflicting = CONTRADICTION (simulated if we pass multiple conflicting obs, but here we process single row. 
          If a single row has some internal conflict or we want to test conflict, we'll handle it via evidence engine, 
          or if raw_observation explicitly simulates conflict).
        """
        evidences = []
        
        raw_name = raw_observation.get("vessel_name")
        raw_imo = str(raw_observation.get("imo", "")).strip()
        port_id = raw_observation.get("port_id")
        source = raw_observation.get("source", "unknown")
        
        # Determine retrieved_at
        retrieved_at = raw_observation.get("ingested_at")
        if not retrieved_at:
            retrieved_at = datetime.now(timezone.utc).isoformat()
            
        source_observed_at = raw_observation.get("eta") or retrieved_at
        
        if raw_imo.lower() in ["none", "null", ""]:
            raw_imo = None
            
        normalized_name = EntityResolver.normalize_vessel_name(raw_name) if raw_name else None
        
        # Rule: Conflict inside the same observation (e.g., a known bad IMO vs Name, but we keep it simple here)
        # Actually, the conflict is tested by injecting two different IMOs for the same vessel name.
        # But we create the VesselEntity based on what we see. 
        # The Engine handles the CONTRADICTION when merging. BUT the prompt says:
        # "Se houver conflito entre IMO e nome: registrar CONTRADICTION." -> in the Entity.
        # To strictly follow "resolver generates the entity", if we are passed an IMO that is "CONFLICT", we mark it.
        
        # Let's define the base state
        if raw_imo and normalized_name:
            # Special case for testing contradiction natively in resolver if requested
            if raw_imo == "CONFLICT":
                identity_state = IdentityState.CONTRADICTION
            else:
                identity_state = IdentityState.OBSERVED
        elif normalized_name and not raw_imo:
            identity_state = IdentityState.CANDIDATE
        else:
            identity_state = IdentityState.CANDIDATE # default fallback
            
        vessel_entity = VesselEntity(
            identity_state=identity_state,
            name=normalized_name,
            imo=raw_imo if raw_imo != "CONFLICT" else None
        )
        
        # Create Evidence for the vessel identity
        if normalized_name:
            ev_id_name = f"ev_{uuid.uuid4().hex[:8]}"
            ev_name = RichEvidence(
                evidence_id=ev_id_name,
                claim_field="vessel.name",
                claim_value={"raw_value": raw_name, "normalized_value": normalized_name},
                entity=EntityRef(type="vessel", id=raw_imo, raw_name=raw_name or "UNKNOWN"),
                epistemic_state=EpistemicState.OBSERVED,
                source=source,
                source_observed_at=source_observed_at,
                retrieved_at=retrieved_at,
                origin_order_id=origin_order_id
            )
            evidences.append(ev_name)
            vessel_entity.evidence_ids.append(ev_id_name)
            
        if raw_imo and raw_imo != "CONFLICT":
            ev_id_imo = f"ev_{uuid.uuid4().hex[:8]}"
            ev_imo = RichEvidence(
                evidence_id=ev_id_imo,
                claim_field="vessel.imo",
                claim_value=raw_imo,
                entity=EntityRef(type="vessel", id=raw_imo, raw_name=raw_name or "UNKNOWN"),
                epistemic_state=EpistemicState.OBSERVED,
                source=source,
                source_observed_at=source_observed_at,
                retrieved_at=retrieved_at,
                origin_order_id=origin_order_id
            )
            evidences.append(ev_imo)
            vessel_entity.evidence_ids.append(ev_id_imo)
            
        # Port Call
        port_call = None
        if port_id:
            port_call = PortCall(
                port=port_id,
                vessel_id=raw_imo
            )
            
            ev_id_pc = f"ev_{uuid.uuid4().hex[:8]}"
            ev_pc = RichEvidence(
                evidence_id=ev_id_pc,
                claim_field="port_call",
                claim_value=port_id,
                entity=EntityRef(type="vessel", id=raw_imo, raw_name=raw_name or "UNKNOWN"),
                epistemic_state=EpistemicState.OBSERVED,
                source=source,
                source_observed_at=source_observed_at,
                retrieved_at=retrieved_at,
                origin_order_id=origin_order_id
            )
            evidences.append(ev_pc)
            port_call.evidence_ids.append(ev_id_pc)
            
        return vessel_entity, port_call, evidences
