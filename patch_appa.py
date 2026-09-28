import re

with open("src/ingestion/live_sources.py", "r") as f:
    content = f.read()

new_scraper = """
# ---------------------------------------------------------------- Portos do Parana (BRPNG)

def fetch_appa_paranagua(timeout: int = 30) -> list:
    \"\"\"Consulta a API JSON pública da APPA (Portos do Paraná) para BRPNG.\"\"\"
    import requests
    linhas = []
    try:
        url = "https://www.appaweb.appa.pr.gov.br/appawebservices/api/ConsultarInformacoesLineUpSite/ConsultarInformacoesLineUpSite"
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            atracados = int(data.get("Atracados", 0))
            ao_largo = int(data.get("AoLargo", 0))
            esperados = int(data.get("Esperados", 0))
            programados = int(data.get("Programados", 0))
            
            # Reconstrói como lista de eventos para o ingestor unificado contar
            linhas.extend([{"status": "ATRACADO", "ship_name": f"APPA_{i}"} for i in range(atracados)])
            linhas.extend([{"status": "AO_LARGO", "ship_name": f"APPA_{i}"} for i in range(ao_largo)])
            linhas.extend([{"status": "ESPERADO", "ship_name": f"APPA_{i}"} for i in range(esperados)])
            linhas.extend([{"status": "PROGRAMADO", "ship_name": f"APPA_{i}"} for i in range(programados)])
    except Exception:
        pass
    return linhas

# ---------------------------------------------------------------- Porto do Itaqui (BRIQI)
"""

content = re.sub(
    r"# ---------------------------------------------------------------- Portos do Parana \(BRPNG\).*?# ---------------------------------------------------------------- Porto do Itaqui \(BRIQI\)",
    new_scraper.strip() + "\n\n# ---------------------------------------------------------------- Porto do Itaqui (BRIQI)",
    content,
    flags=re.DOTALL
)

with open("src/ingestion/live_sources.py", "w") as f:
    f.write(content)
print("APPA Paranagua scraper implemented!")
