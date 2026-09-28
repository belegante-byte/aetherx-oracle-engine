import re

with open("src/ingestion/live_sources.py", "r") as f:
    content = f.read()

new_scrapers = """
# ---------------------------------------------------------------- Portos do Parana (BRPNG)

def fetch_appa_paranagua(timeout: int = 30) -> list:
    \"\"\"Raspa o painel da APPA (Portos do Paraná) para BRPNG.
    (Stub de implementacao MVP para extração HTML)
    \"\"\"
    return []

# ---------------------------------------------------------------- Porto do Itaqui (BRIQI)

def fetch_emar_itaqui(timeout: int = 30) -> list:
    \"\"\"Raspa o painel do Porto do Itaqui (Maranhão) para BRIQI.
    (Stub de implementacao MVP para extração HTML)
    \"\"\"
    return []

# ---------------------------------------------------------------- ShipInfo (AIS global)
"""

content = re.sub(
    r"# ---------------------------------------------------------------- ShipInfo \(AIS global\)",
    new_scrapers.strip(),
    content
)

# Add to coletar_tudo
content = content.replace(
    '        "cdp_viladoconde": fetch_cdp_viladoconde,',
    '        "cdp_viladoconde": fetch_cdp_viladoconde,\n        "appa_paranagua": fetch_appa_paranagua,\n        "emar_itaqui": fetch_emar_itaqui,'
)

# Add to SOURCE_LABELS
content = content.replace(
    '    "cdp_viladoconde": "CDP (Vila do Conde)",',
    '    "cdp_viladoconde": "CDP (Vila do Conde)",\n    "appa_paranagua": "APPA (Portos do Paraná)",\n    "emar_itaqui": "Porto do Itaqui (EMAP)",'
)

with open("src/ingestion/live_sources.py", "w") as f:
    f.write(content)
print("BRPNG e BRIQI stubs adicionados.")
