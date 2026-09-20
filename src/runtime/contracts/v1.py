from typing import Any, List, Dict, Optional
from pydantic import BaseModel, Field


class Entity(BaseModel):
    """Representação genérica de entidade identificada (vessel, port, terminal, etc)."""
    type: str
    id: str
    attributes: Dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    """Evidência física de observação e proveniência auditável."""
    source: str
    timestamp: str
    raw_payload: Optional[str] = None
    confidence: float = 1.0


class Observation(BaseModel):
    """Observação pura de estado de uma entidade."""
    entity: Entity
    observed_at: str
    evidence: List[Evidence] = Field(default_factory=list)


class StateTransition(BaseModel):
    """Transição observada entre estados."""
    field: str
    from_value: Optional[Any] = None
    to_value: Optional[Any] = None


class PhysicalEvent(BaseModel):
    """Evento físico temporal representando mutação de estado (physical-event.v1)."""
    schema_version: str = "physical-event.v1"
    event_id: str
    event_type: str  # ex: VESSEL_STATUS_CHANGED, VESSEL_FIRST_OBSERVED, LAND_QUEUE_UPDATED
    entity: Entity
    transition: Optional[StateTransition] = None
    observed_at: str
    evidence: List[Evidence] = Field(default_factory=list)


class ChangePacket(BaseModel):
    """Pacote temporal de alterações logísticas (change-packet.v1)."""
    schema_version: str = "change-packet.v1"
    packet_id: str
    generated_at: str
    events: List[PhysicalEvent] = Field(default_factory=list)


class ClientContext(BaseModel):
    """Contexto de identidade e autorização do cliente M2M."""
    request_id: str = ""
    client_id: str
    access_mode: str  # legacy | authenticated
    product: str = "gp5"
    permissions: List[str] = Field(default_factory=list)

    def has_permission(self, permission: str) -> bool:
        """Verifica se o cliente possui uma permissão específica.
        Suporta wildcard: 'decision.*' cobre 'decision.charter_risk' etc.
        """
        if permission in self.permissions:
            return True
        prefix = permission.rsplit(".", 1)[0] + ".*"
        return prefix in self.permissions



class UsageEvent(BaseModel):
    """Evento de instrumentação e medição de uso M2M (usage-event.v1)."""
    schema_version: str = "usage-event.v1"
    request_id: str
    client_id: str
    product: str
    tool: str
    access_mode: str
    timestamp: str
    duration_ms: int
    status_code: int


class DecisionResult(BaseModel):
    """Resultado estruturado de suporte à decisão (decision-result.v1)."""
    schema_version: str = "decision-result.v1"
    decision_id: str
    evaluated_at: str
    exposure: Dict[str, Any] = Field(default_factory=dict)
    assumptions: Dict[str, Any] = Field(default_factory=dict)
    physical_basis: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    comparison: Optional[Dict[str, Any]] = None
