import copy
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.api.main import app, PRODUCTION_URL


EXAMPLE_RESPONSE = {
    "port_id": "BRSSZ",
    "port_name": "Santos",
    "country": "Brasil",
    "congestion_score": 0.78,
    "eta_delay_days": 1.6,
    "waiting_vessels": 12,
    "freight_volatility_index": 0.42,
    "updated_at": "2026-09-17 15:46:53",
}

RESPONSE_SCHEMA = {
    "type": "object",
    "required": [
        "port_id", "port_name", "country", "congestion_score",
        "eta_delay_days", "waiting_vessels", "freight_volatility_index", "updated_at",
    ],
    "properties": {
        "port_id": {"type": "string", "example": "BRSSZ"},
        "port_name": {"type": "string", "example": "Santos"},
        "country": {"type": "string", "example": "Brasil"},
        "congestion_score": {"type": "number", "format": "double", "example": 0.78},
        "eta_delay_days": {"type": "number", "format": "double", "example": 1.6},
        "waiting_vessels": {"type": "integer", "example": 12},
        "freight_volatility_index": {"type": "number", "format": "double", "example": 0.42},
        "updated_at": {"type": "string", "example": "2026-09-17 15:46:53"},
    },
}


def _minimal_spec():
    """Spec mínima e autossuficiente para máxima compatibilidade com o importador RapidAPI."""
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Aether-X Port Congestion Oracle",
            "description": "Algorithmic predictive port delay & congestion scores for global trade and quantitative funds.",
            "version": "0.2.0",
        },
        "servers": [{"url": PRODUCTION_URL, "description": "Production (Railway)"}],
        "paths": {
            "/v1/port-risk": {
                "get": {
                    "summary": "Get Port Risk",
                    "description": "Returns the predictive congestion signal for a given global port.",
                    "operationId": "getPortRisk",
                    "parameters": [
                        {
                            "name": "port_id",
                            "in": "query",
                            "required": True,
                            "description": "UN/LOCODE do porto (ex: BRSSZ - Santos, CNSHA - Shanghai)",
                            "schema": {"type": "string", "example": "BRSSZ"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Successful Response",
                            "content": {
                                "application/json": {
                                    "schema": RESPONSE_SCHEMA,
                                    "example": EXAMPLE_RESPONSE,
                                }
                            },
                        }
                    },
                }
            }
        },
    }


def generate_openapi():
    docs_dir = "docs"
    os.makedirs(docs_dir, exist_ok=True)

    openapi_data = app.openapi()

    native_path = os.path.join(docs_dir, "openapi.json")
    with open(native_path, "w", encoding="utf-8") as f:
        json.dump(openapi_data, f, indent=2)
    print(f"[AETHER-X DOCS] Especificação OpenAPI (3.1.0) gerada em: {native_path}")

    # Spec curada e compatível com o importador do RapidAPI
    rapidapi = copy.deepcopy(openapi_data)
    rapidapi["openapi"] = "3.0.3"
    rapidapi["servers"] = [{"url": PRODUCTION_URL, "description": "Production (Railway)"}]

    for path_item in rapidapi["paths"].values():
        for operation in path_item.values():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            operation["responses"].pop("422", None)
            resp_200 = operation["responses"].get("200")
            if resp_200 and "content" in resp_200:
                resp_200["content"]["application/json"]["example"] = EXAMPLE_RESPONSE

    schemas = rapidapi.get("components", {}).get("schemas", {})
    for unused in ("HTTPValidationError", "ValidationError"):
        schemas.pop(unused, None)

    rapidapi_path = os.path.join(docs_dir, "openapi.rapidapi.json")
    with open(rapidapi_path, "w", encoding="utf-8") as f:
        json.dump(rapidapi, f, indent=2)
    print(f"[AETHER-X DOCS] Especificação OpenAPI (3.0.3 / RapidAPI) gerada em: {rapidapi_path}")

    minimal_path = os.path.join(docs_dir, "openapi.rapidapi.min.json")
    with open(minimal_path, "w", encoding="utf-8") as f:
        json.dump(_minimal_spec(), f, indent=2)
    print(f"[AETHER-X DOCS] Especificação OpenAPI (3.0.3 / RapidAPI minimal) gerada em: {minimal_path}")


if __name__ == "__main__":
    generate_openapi()