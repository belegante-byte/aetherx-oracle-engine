import copy
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.api.main import app, API_DESCRIPTION, PRODUCTION_URL
from src.engine.risk_model import calculate_port_risk, calculate_port_trend

LOGO_URL = "https://raw.githubusercontent.com/belegante-byte/aetherx-mcp/main/assets/logo.png"

# Exemplos derivados do motor real para nunca divergirem da implementação
EXAMPLE_RESPONSE = calculate_port_risk("BRSSZ")
EXAMPLE_TREND_RESPONSE = calculate_port_trend("BRSSZ")

RESPONSE_SCHEMA = {
    "type": "object",
    "required": [
        "port_id", "port_name", "country", "congestion_score",
        "eta_delay_days", "waiting_vessels", "freight_volatility_index",
        "estimated_daily_demurrage_usd", "updated_at",
    ],
    "properties": {
        "port_id": {"type": "string", "example": "BRSSZ"},
        "port_name": {"type": "string", "example": "Santos"},
        "country": {"type": "string", "example": "Brasil"},
        "congestion_score": {"type": "number", "format": "double", "example": 0.78},
        "eta_delay_days": {"type": "number", "format": "double", "example": 1.6},
        "waiting_vessels": {"type": "integer", "example": 12},
        "freight_volatility_index": {"type": "number", "format": "double", "example": 0.42},
        "estimated_daily_demurrage_usd": {"type": "integer", "example": 63200},
        "updated_at": {"type": "string", "example": "2026-09-17 15:46:53"},
    },
}

TREND_PROJECTION_SCHEMA = {
    "type": "object",
    "required": ["congestion_score", "eta_delay_days", "estimated_daily_demurrage_usd"],
    "properties": {
        "congestion_score": {"type": "number", "format": "double"},
        "eta_delay_days": {"type": "number", "format": "double"},
        "estimated_daily_demurrage_usd": {"type": "integer"},
    },
}

TREND_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["port_id", "port_name", "country", "trend", "congestion_score", "projection", "updated_at"],
    "properties": {
        "port_id": {"type": "string", "example": "BRSSZ"},
        "port_name": {"type": "string", "example": "Santos"},
        "country": {"type": "string", "example": "Brasil"},
        "trend": {"type": "string", "enum": ["acelerando", "estável", "descongestionando"], "example": "estável"},
        "congestion_score": {"type": "number", "format": "double", "example": 0.78},
        "projection": {
            "type": "object",
            "additionalProperties": TREND_PROJECTION_SCHEMA,
        },
        "updated_at": {"type": "string", "example": "2026-09-17 15:46:53"},
    },
}


def _minimal_spec():
    """Spec mínima e autossuficiente para máxima compatibilidade com o importador RapidAPI."""
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Aether-X Port Congestion Oracle",
            "description": API_DESCRIPTION,
            "version": "0.2.0",
            "termsOfService": f"{PRODUCTION_URL}/terms",
            "contact": {
                "name": "Aether-X",
                "url": PRODUCTION_URL,
                "email": "contato@aether-grid.io",
            },
            "x-logo": {"url": LOGO_URL, "altText": "Aether-X Port Congestion Oracle"},
        },
        "servers": [{"url": PRODUCTION_URL, "description": "Production (Railway)"}],
        "tags": [
            {
                "name": "Port Risk",
                "description": "Predictive congestion, ETA delay and freight volatility signals per port.",
            }
        ],
        "paths": {
            "/v1/port-risk": {
                "get": {
                    "tags": ["Port Risk"],
                    "summary": "Get port risk",
                    "description": (
                        "Returns the predictive congestion signal for a single global port: "
                        "`congestion_score` (0.0-1.0), `eta_delay_days`, `waiting_vessels` and "
                        "`freight_volatility_index`. Unknown ports return a global statistical "
                        'estimate with `country="Global"`.'
                    ),
                    "operationId": "getPortRisk",
                    "parameters": [
                        {
                            "name": "port_id",
                            "in": "query",
                            "required": True,
                            "description": "UN/LOCODE of the port, e.g. BRSSZ (Santos), CNSHA (Shanghai), NLRTM (Rotterdam).",
                            "schema": {"type": "string", "example": "BRSSZ"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "The current congestion signal for the requested port.",
                            "content": {
                                "application/json": {
                                    "schema": RESPONSE_SCHEMA,
                                    "example": EXAMPLE_RESPONSE,
                                }
                            },
                        }
                    },
                }
            },
            "/v1/port-trend": {
                "get": {
                    "tags": ["Port Risk"],
                    "summary": "Get port risk trend",
                    "description": (
                        "Returns the 24h, 48h and 72h congestion projections for a single "
                        "global port, with a `trend` label (`acelerando`, `estável` or "
                        "`descongestionando`)."
                    ),
                    "operationId": "getPortTrend",
                    "parameters": [
                        {
                            "name": "port_id",
                            "in": "query",
                            "required": True,
                            "description": "UN/LOCODE of the port, e.g. BRSSZ (Santos), CNSHA (Shanghai), NLRTM (Rotterdam).",
                            "schema": {"type": "string", "example": "BRSSZ"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "The 24h, 48h and 72h congestion projections for the requested port.",
                            "content": {
                                "application/json": {
                                    "schema": TREND_RESPONSE_SCHEMA,
                                    "example": EXAMPLE_TREND_RESPONSE,
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
    rapidapi["info"]["x-logo"] = {"url": LOGO_URL, "altText": "Aether-X Port Congestion Oracle"}

    examples_by_path = {
        "/v1/port-risk": EXAMPLE_RESPONSE,
        "/v1/port-trend": EXAMPLE_TREND_RESPONSE,
    }
    for path, path_item in rapidapi["paths"].items():
        for operation in path_item.values():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            operation["responses"].pop("422", None)
            resp_200 = operation["responses"].get("200")
            if resp_200 and "content" in resp_200:
                resp_200["content"]["application/json"]["example"] = examples_by_path.get(
                    path, EXAMPLE_RESPONSE
                )

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