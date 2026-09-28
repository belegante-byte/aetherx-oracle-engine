with open("src/ingestion/land_sources.py", "r") as f:
    content = f.read()

new_content = """import os
from typing import List, Dict, Any

# DESATIVADO no MVP: integração real requer contratos EDI de R$ 50k+/mês.
# Mantido apenas como stub para manter assinatura da API.
IS_MOCK = True

def fetch_rumo_operations(allow_mock: bool = False) -> List[Dict[str, Any]]:
    return []
"""

with open("src/ingestion/land_sources.py", "w") as f:
    f.write(new_content)
print("Land sources patched.")
