from typing import Any, Dict
from src.runtime.contracts.v1 import Entity


def create_entity(entity_type: str, entity_id: str, attributes: Dict[str, Any] = None) -> Entity:
    """Cria uma entidade genérica identificada."""
    return Entity(
        type=str(entity_type).strip().lower(),
        id=str(entity_id).strip().upper(),
        attributes=attributes or {}
    )
