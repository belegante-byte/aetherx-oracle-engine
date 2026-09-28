import re

with open("src/ingestion/live_sources.py", "r") as f:
    content = f.read()

new_scraper = """
# ---------------------------------------------------------------- CDP (Vila do Conde)

CDP_SCAP_URL = "http://scap.cdp.com.br:8047/webrun/open.do?action=open&sys=SCAP"

def fetch_cdp_viladoconde(timeout: int = 30) -> list:
    \"\"\"Raspa o painel da Companhia Docas do Pará para BRVDC.
    (Implementação MVP: stub focado na frota da Vale e Norsk Hydro)
    
    Atenção: O sistema SCAP da CDP utiliza Webrun Enterprise (Java). 
    A extração exigirá simulação de sessão (cookies JSESSIONID) e 
    postback para acessar o relatório tabular de 'Programação de Navios'.
    \"\"\"
    return []

# ---------------------------------------------------------------- ShipInfo (AIS global)
"""

content = re.sub(
    r"# ---------------------------------------------------------------- CDP \(Vila do Conde\).*?# ---------------------------------------------------------------- ShipInfo \(AIS global\)",
    new_scraper.strip() + "\n\n# ---------------------------------------------------------------- ShipInfo (AIS global)",
    content,
    flags=re.DOTALL
)

with open("src/ingestion/live_sources.py", "w") as f:
    f.write(content)
print("CDP Vila do Conde atualizado com endpoint SCAP.")
