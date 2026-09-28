import re

with open("src/ingestion/live_sources.py", "r") as f:
    content = f.read()

new_scraper = """
# ---------------------------------------------------------------- Portos RS (Rio Grande)

PORTOSRS_URL = "https://www.portosrs.com.br/site/relatorios-diarios"

def fetch_portosrs_riogrande(timeout: int = 30) -> list:
    \"\"\"Raspa o painel da Portos RS para BRRGD.
    (Implementação MVP: stub aguardando parse detalhado do HTML)
    \"\"\"
    return []

# ---------------------------------------------------------------- ShipInfo (AIS global)
"""

content = content.replace("# ---------------------------------------------------------------- ShipInfo (AIS global)", new_scraper)

# Add to coletar_tudo
content = content.replace(
    '        "portosrio_silog": fetch_portosrio_silog,',
    '        "portosrio_silog": fetch_portosrio_silog,\n        "portosrs_riogrande": fetch_portosrs_riogrande,'
)

# Add to SOURCE_LABELS
content = content.replace(
    '    "portosrio_silog": "SILOG PortosRio (Rio de Janeiro, Niterói, Itaguaí)",',
    '    "portosrio_silog": "SILOG PortosRio (Rio de Janeiro, Niterói, Itaguaí)",\n    "portosrs_riogrande": "Portos RS (Rio Grande)",'
)

with open("src/ingestion/live_sources.py", "w") as f:
    f.write(content)
print("live_sources patched.")
