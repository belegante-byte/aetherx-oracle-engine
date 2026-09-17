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


if __name__ == "__main__":
    generate_openapi()