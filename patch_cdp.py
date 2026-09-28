import re

with open("src/ingestion/live_sources.py", "r") as f:
    content = f.read()

new_scraper = """
# ---------------------------------------------------------------- CDP (Vila do Conde)

CDP_URL = "http://www.cdp.com.br/sistemas/programacao-de-navios"

def fetch_cdp_viladoconde(timeout: int = 30) -> list:
    \"\"\"Raspa o painel da Companhia Docas do Pará para BRVDC.
    (Implementação MVP: stub focado na frota da Vale e Norsk Hydro)
    \"\"\"
    return []

# ---------------------------------------------------------------- ShipInfo (AIS global)
"""

content = content.replace("# ---------------------------------------------------------------- ShipInfo (AIS global)", new_scraper)

# Add to coletar_tudo
content = content.replace(
    '        "portosrs_riogrande": fetch_portosrs_riogrande,',
    '        "portosrs_riogrande": fetch_portosrs_riogrande,\n        "cdp_viladoconde": fetch_cdp_viladoconde,'
)

# Add to SOURCE_LABELS
content = content.replace(
    '    "portosrs_riogrande": "Portos RS (Rio Grande)",',
    '    "portosrs_riogrande": "Portos RS (Rio Grande)",\n    "cdp_viladoconde": "CDP (Vila do Conde)",'
)

with open("src/ingestion/live_sources.py", "w") as f:
    f.write(content)
print("CDP Vila do Conde stub adicionado.")
