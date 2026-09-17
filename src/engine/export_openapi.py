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
    output_path = os.path.join(docs_dir, "openapi.json")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_data, f, indent=2)
        
    print(f"[AETHER-X DOCS] Especificação OpenAPI gerada com sucesso em: {output_path}")


if __name__ == "__main__":
    generate_openapi()