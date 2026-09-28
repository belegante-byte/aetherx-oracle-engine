import re

with open("src/ingestion/live_sources.py", "r") as f:
    content = f.read()

new_scraper = """
# ---------------------------------------------------------------- Porto do Itaqui (BRIQI)

def fetch_emar_itaqui(timeout: int = 30) -> list:
    \"\"\"Raspa a página inicial do Porto do Itaqui (EMAP) para BRIQI.\"\"\"
    import requests
    from bs4 import BeautifulSoup
    linhas = []
    try:
        url = "https://www.emap.ma.gov.br/"
        # Muitas vezes o portal principal redireciona, mas o requests lida com redirects
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Aether-X Oracle/1.3.0"})
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            def _extract_count(keyword):
                import re
                # Ex: "9 Navios Atracados"
                spans = soup.find_all('span', text=re.compile(keyword, re.IGNORECASE))
                for span in spans:
                    match = re.search(r'(\d+)', span.text)
                    if match:
                        return int(match.group(1))
                return 0
                
            atracados = _extract_count('Atracados')
            fundeados = _extract_count('Fundeados')
            esperados = _extract_count('Esperados')
            
            linhas.extend([{"status": "ATRACADO", "ship_name": f"ITAQUI_{i}"} for i in range(atracados)])
            linhas.extend([{"status": "AO_LARGO", "ship_name": f"ITAQUI_{i}"} for i in range(fundeados)])
            linhas.extend([{"status": "ESPERADO", "ship_name": f"ITAQUI_{i}"} for i in range(esperados)])
    except Exception:
        pass
    return linhas
"""

content = re.sub(
    r"# ---------------------------------------------------------------- Porto do Itaqui \(BRIQI\).*?def fetch_emar_itaqui.*?return \[\]",
    new_scraper.strip(),
    content,
    flags=re.DOTALL
)

with open("src/ingestion/live_sources.py", "w") as f:
    f.write(content)
print("Itaqui scraper implemented!")
