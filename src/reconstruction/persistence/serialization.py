import json
from src.reconstruction.models import RichEvidence, ShipmentReconstruction, VesselEntity, PortCall, Voyage

def evidence_to_dict(ev: RichEvidence) -> dict:
    return ev.model_dump(mode='json')

def evidence_from_dict(d: dict) -> RichEvidence:
    return RichEvidence.model_validate(d)

def shipment_to_json(shipment: ShipmentReconstruction) -> str:
    return shipment.model_dump_json()

def shipment_from_json(json_str: str) -> ShipmentReconstruction:
    return ShipmentReconstruction.model_validate_json(json_str)

def entity_to_json(entity) -> str:
    return entity.model_dump_json()
