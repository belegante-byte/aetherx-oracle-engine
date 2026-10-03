import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class EpistemicState(str, Enum):
    OBSERVED = "observed"
    DERIVED = "derived"
    ESTIMATED = "estimated"
    INFERRED = "inferred"
    HYPOTHESIS = "hypothesis"
    UNKNOWN = "unknown"
    CONTRADICTION = "contradiction"
    RETRACTED = "retracted"

class IdentityState(str, Enum):
    OBSERVED = "observed"
    CANDIDATE = "candidate"
    CONTRADICTION = "contradiction"

class EntityRef(BaseModel):
    type: str
    id: Optional[str] = None
    raw_name: str

class RichEvidence(BaseModel):
    evidence_id: str
    claim_field: str
    claim_value: Any
    entity: EntityRef
    
    epistemic_state: EpistemicState
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    source: str
    source_observed_at: Optional[str] = None
    retrieved_at: str
    
    origin_order_id: Optional[str] = None

    @property
    def logical_id(self) -> str:
        import hashlib
        import json
        
        cv = json.dumps(self.claim_value, sort_keys=True) if isinstance(self.claim_value, dict) else str(self.claim_value)
            
        components = [
            self.source,
            self.claim_field,
            cv,
            str(self.source_observed_at or ""),
            str(self.entity.id or self.entity.raw_name)
        ]
        base_str = "|".join(components)
        return hashlib.sha256(base_str.encode("utf-8")).hexdigest()

class VesselEntity(BaseModel):
    identity_state: IdentityState
    name: Optional[str] = None
    imo: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)

    @property
    def stable_id(self) -> str:
        if self.imo:
            return f"urn:vessel:imo:{self.imo}"
        elif self.name:
            import hashlib
            name_hash = hashlib.md5(self.name.encode('utf-8')).hexdigest()[:8]
            return f"urn:vessel:name:{name_hash}"
        return "urn:vessel:unknown"

class PortCall(BaseModel):
    port: str
    vessel_id: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    
    @property
    def stable_id(self) -> str:
        v_id = self.vessel_id or "unknown"
        return f"urn:portcall:{self.port}:{v_id}"

class ShipmentHypothesis(BaseModel):
    hypothesis_id: str
    claim_field: str
    claim_value: Any
    epistemic_state: EpistemicState
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    conflicting_evidence_ids: List[str] = Field(default_factory=list)
    rationale: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: str
    provenance: str

    @property
    def stable_id(self) -> str:
        import hashlib
        # Hypotheses are deduplicated by their core claim and supporting evidence
        sup_str = ",".join(sorted(self.supporting_evidence_ids))
        base_str = f"{self.claim_field}:{self.claim_value}:{sup_str}"
        return f"urn:hypothesis:{hashlib.md5(base_str.encode('utf-8')).hexdigest()[:8]}"

class Voyage(BaseModel):
    voyage_id: str
    vessel_id: str
    port_call_ids: List[str] = Field(default_factory=list)
    
    @property
    def stable_id(self) -> str:
        return f"urn:voyage:{self.voyage_id}"

class ShipmentField(BaseModel):
    current_value: Any = None
    state: EpistemicState = EpistemicState.UNKNOWN
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    conflicting_evidence_ids: List[str] = Field(default_factory=list)
    retracted_evidence_ids: List[str] = Field(default_factory=list)

class ShipmentReconstruction(BaseModel):
    """
    ShipmentReconstruction is a PARTIAL and EPISTEMICALLY QUALIFIED view of a logistical flow.
    It does not necessarily represent a single commercial Bill of Lading (BL) or physical cargo load.
    It acts as an accumulator for evidence regarding cargo, parties, and routing tied to an operational trigger.
    
    Currently, the pipeline uses a 1:1 mapping (urn:shipment:{portcall_id}) as a provisional operational aggregator.
    However, the domain supports 1 PortCall -> N Shipments natively.
    """
    shipment_id: str
    
    vessel: ShipmentField = Field(default_factory=ShipmentField)
    origin_port: ShipmentField = Field(default_factory=ShipmentField)
    destination_port: ShipmentField = Field(default_factory=ShipmentField)
    port_call: ShipmentField = Field(default_factory=ShipmentField)
    voyage: ShipmentField = Field(default_factory=ShipmentField)
    cargo: ShipmentField = Field(default_factory=ShipmentField)
    shipper: ShipmentField = Field(default_factory=ShipmentField)
    consignee: ShipmentField = Field(default_factory=ShipmentField)
    status: ShipmentField = Field(default_factory=ShipmentField)
    
    evidence_store: Dict[str, RichEvidence] = Field(default_factory=dict)
    hypotheses: Dict[str, ShipmentHypothesis] = Field(default_factory=dict)
    
    @property
    def stable_id(self) -> str:
        return f"urn:shipment:{self.shipment_id}"

class OperationalOrder(BaseModel):
    order_id: str
    consumer: str
    issued_at: str
    objective: str
    parameters: Dict[str, Any]
    evidence_generated: List[RichEvidence] = Field(default_factory=list)
