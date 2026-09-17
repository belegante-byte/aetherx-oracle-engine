import copy
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.api.main import app


def generate_openapi():
    docs_dir = "docs"
    os.makedirs(docs_dir, exist_ok=True)

    openapi_data = app.openapi()

    native_path = os.path.join(docs_dir, "openapi.json")
    with open(native_path, "w", encoding="utf-8") as f:
        json.dump(openapi_data, f, indent=2)
    print(f"[AETHER-X DOCS] Especificação OpenAPI (3.1.0) gerada em: {native_path}")

    # Cópia compatível com o importador do RapidAPI (que não aceita OpenAPI 3.1)
    rapidapi_data = copy.deepcopy(openapi_data)
    rapidapi_data["openapi"] = "3.0.3"
    rapidapi_path = os.path.join(docs_dir, "openapi.rapidapi.json")
    with open(rapidapi_path, "w", encoding="utf-8") as f:
        json.dump(rapidapi_data, f, indent=2)
    print(f"[AETHER-X DOCS] Especificação OpenAPI (3.0.3 / RapidAPI) gerada em: {rapidapi_path}")


if __name__ == "__main__":
    generate_openapi()