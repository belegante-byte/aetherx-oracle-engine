from typing import Any, Dict
from pydantic import BaseModel


def format_m2m_response(data: Any, schema_version: str = "v1") -> Dict[str, Any]:
    """Padroniza a resposta serializada para interfaces MCP e REST M2M."""
    if isinstance(data, BaseModel):
        payload = data.model_dump()
    elif isinstance(data, dict):
        payload = data
    else:
        payload = {"result": data}
        
    if "schema_version" not in payload:
        payload["schema_version"] = schema_version
        
    return payload
