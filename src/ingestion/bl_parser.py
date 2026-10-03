from typing import Any, Dict, Tuple
from src.reconstruction.models import EpistemicState

def parse_bl_static(payload: dict) -> Dict[str, Tuple[Any, EpistemicState, str]]:
    """
    Realiza o parse de um payload bruto de Bill of Lading (BL).
    Retorna dicionário mapeando nome do campo para (valor, EpistemicState, provenance).
    """
    mandatory = ["consignee", "destination_port"]
    optional = ["shipper", "vessel", "cargo"]
    
    # O dataset da Ordem 19 tinha 'destination'
    if "destination" in payload and "destination_port" not in payload:
        payload["destination_port"] = payload["destination"]
        
    result = {}
    
    for field in mandatory:
        val = payload.get(field)
        if val is not None and str(val).strip() != "":
            result[field] = (val, EpistemicState.OBSERVED, "BL_STATIC")
        else:
            result[field] = (None, EpistemicState.UNKNOWN, "BL_STATIC")
            
    for field in optional:
        val = payload.get(field)
        if val is not None and str(val).strip() != "":
            result[field] = (val, EpistemicState.OBSERVED, "BL_STATIC")
            
    return result
