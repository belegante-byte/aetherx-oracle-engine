import copy
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.api.main import app, API_DESCRIPTION, PRODUCTION_URL, APP_VERSION
from src.engine.risk_model import calculate_port_risk, calculate_port_trend

LOGO_URL = "https://raw.githubusercontent.com/belegante-byte/aetherx-mcp/main/assets/logo.png"

# Exemplos derivados do motor real para nunca divergirem da implementação
EXAMPLE_RESPONSE = calculate_port_risk("BRSSZ")
EXAMPLE_TREND_RESPONSE = calculate_port_trend("BRSSZ")
EXAMPLE_BATCH_RESPONSE = {
    "results": [EXAMPLE_RESPONSE, calculate_port_risk("CNSHA")]
}

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
        # Calibração v1 (observação de fila ↔ série ANTAQ). None quando o porto
        # não tem janela ANTAQ: ausência de valor é publicada como ausência.
        "historical_expected_wait_h": {
            "type": "number", "format": "double", "nullable": True, "example": 183.0,
            "description": "Median (p50) expected wait in hours, calibrated against the ANTAQ series.",
        },
        "p90_wait_h": {
            "type": "number", "format": "double", "nullable": True, "example": 590.4,
            "description": "90th-percentile expected wait in hours.",
        },
        "expected_demurrage_usd": {
            "type": "integer", "nullable": True, "example": 244000,
            "description": "Parametric demurrage exposure at p50 (USD), under a declared reference daily rate.",
        },
        "p90_demurrage_usd": {
            "type": "integer", "nullable": True, "example": 787199,
            "description": "Parametric demurrage exposure at p90 (USD).",
        },
        "confidence": {
            "type": "number", "format": "double", "nullable": True, "example": 0.8,
            "description": "Calibration confidence (0.0-1.0), computed by formula v1. Never a fixed constant.",
        },
        "paired_windows": {
            "type": "integer", "nullable": True, "example": 5,
            "description": "Number of matched observation-ANTAQ windows backing the calibration.",
        },
        "calibration_status": {
            "type": "string", "nullable": True, "example": "LIMITED",
            "enum": ["CALIBRATED", "QUALIFIED", "LIMITED", "INSUFFICIENT"],
            "description": "Calibration maturity. INSUFFICIENT means no paired window; no number is published in that case.",
        },
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

BATCH_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["results"],
    "properties": {
        "results": {"type": "array", "items": RESPONSE_SCHEMA},
    },
}


def _minimal_spec():
    """Spec mínima e autossuficiente para máxima compatibilidade com o importador RapidAPI."""
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Aether-X Port Delay Intelligence",
            "description": API_DESCRIPTION,
            "version": APP_VERSION,
            "termsOfService": f"{PRODUCTION_URL}/terms",
            "contact": {
                "name": "Aether-X",
                "url": PRODUCTION_URL,
                "email": "contact@aether-grid.io",
            },
            "x-logo": {"url": LOGO_URL, "altText": "Aether-X Port Delay Intelligence"},
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
            },
            "/v1/ports-risk": {
                "get": {
                    "tags": ["Port Risk"],
                    "summary": "Get congestion risk for multiple ports in one call",
                    "description": (
                        "Returns the congestion signals for up to 20 ports in a single "
                        "request, preserving the order of the `port_ids` (comma-separated "
                        "UN/LOCODEs)."
                    ),
                    "operationId": "getPortsRisk",
                    "parameters": [
                        {
                            "name": "port_ids",
                            "in": "query",
                            "required": True,
                            "description": "Comma-separated UN/LOCODEs, e.g. BRSSZ,CNSHA,NLRTM (max 20).",
                            "schema": {"type": "string", "example": "BRSSZ,CNSHA,NLRTM"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "The congestion signals, one per requested port.",
                            "content": {
                                "application/json": {
                                    "schema": BATCH_RESPONSE_SCHEMA,
                                    "example": EXAMPLE_BATCH_RESPONSE,
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
    rapidapi["info"]["x-logo"] = {"url": LOGO_URL, "altText": rapidapi["info"]["title"]}

    examples_by_path = {
        "/v1/port-risk": EXAMPLE_RESPONSE,
        "/v1/port-trend": EXAMPLE_TREND_RESPONSE,
        "/v1/ports-risk": EXAMPLE_BATCH_RESPONSE,
    }
    for path, path_item in rapidapi["paths"].items():
        for operation in path_item.values():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            operation["responses"].pop("422", None)
            resp_200 = operation["responses"].get("200")
            if (
                resp_200
                and path in examples_by_path
                and "application/json" in resp_200.get("content", {})
            ):
                resp_200["content"]["application/json"]["example"] = examples_by_path[path]

    schemas = rapidapi.get("components", {}).get("schemas", {})
    for unused in ("HTTPValidationError", "ValidationError"):
        schemas.pop(unused, None)

    # Sanitização OpenAPI 3.0 estrita: o importador do RapidAPI rejeita
    # construtos 3.1 que o FastAPI emite mesmo com openapi="3.0.3".
    #   - anyOf/oneOf com {type: null}  -> nullable: true no tipo real
    #   - "examples": [...] (array)     -> "example": <primeiro> (singular)
    def _sanitize_30(node):
        if isinstance(node, dict):
            for key in ("anyOf", "oneOf"):
                branch = node.get(key)
                if isinstance(branch, list):
                    non_null = [b for b in branch if isinstance(b, dict) and b.get("type") != "null"]
                    has_null = any(isinstance(b, dict) and b.get("type") == "null" for b in branch)
                    if has_null and len(non_null) == 1:
                        merged = dict(non_null[0])
                        merged["nullable"] = True
                        node.pop(key, None)
                        for k, v in merged.items():
                            node[k] = v
                    elif has_null and len(non_null) == 0:
                        node.pop(key, None)
                        node["nullable"] = True
            if "examples" in node and isinstance(node["examples"], list) and "example" not in node:
                if node["examples"]:
                    node["example"] = node["examples"][0]
                del node["examples"]
            for v in node.values():
                _sanitize_30(v)
        elif isinstance(node, list):
            for v in node:
                _sanitize_30(v)

    _sanitize_30(rapidapi)

    rapidapi_path = os.path.join(docs_dir, "openapi.rapidapi.json")
    with open(rapidapi_path, "w", encoding="utf-8") as f:
        json.dump(rapidapi, f, indent=2)
    print(f"[AETHER-X DOCS] Especificação OpenAPI (3.0.3 / RapidAPI) gerada em: {rapidapi_path}")

    root_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "openapi.rapidapi.json")
    with open(root_path, "w", encoding="utf-8") as f:
        json.dump(rapidapi, f, indent=2)
    print(f"[AETHER-X DOCS] Especificação OpenAPI (3.0.3 / RapidAPI) exportada na raiz: {root_path}")

    minimal_path = os.path.join(docs_dir, "openapi.rapidapi.min.json")
    with open(minimal_path, "w", encoding="utf-8") as f:
        json.dump(_minimal_spec(), f, indent=2)
    print(f"[AETHER-X DOCS] Especificação OpenAPI (3.0.3 / RapidAPI minimal) gerada em: {minimal_path}")


if __name__ == "__main__":
    generate_openapi()