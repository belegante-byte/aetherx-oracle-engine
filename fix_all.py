import re

with open("src/ingestion/live_sources.py", "r") as f:
    content = f.read()

# Fix APPA
match_appa = re.search(r'(linhas\.extend\(\[\{"port_id": "BRPNG".*?)except', content, re.DOTALL)
if match_appa:
    block = match_appa.group(1)
    clean_block = ""
    clean_block += '            linhas.extend([{"port_id": "BRPNG", "source": "appa_paranagua", "status": "atracado", "ship_name": f"APPA_{i}"} for i in range(atracados)])\n'
    clean_block += '            linhas.extend([{"port_id": "BRPNG", "source": "appa_paranagua", "status": "ao_largo", "ship_name": f"APPA_{i}"} for i in range(ao_largo)])\n'
    clean_block += '            linhas.extend([{"port_id": "BRPNG", "source": "appa_paranagua", "status": "esperado", "ship_name": f"APPA_{i}"} for i in range(esperados)])\n'
    clean_block += '            linhas.extend([{"port_id": "BRPNG", "source": "appa_paranagua", "status": "programado", "ship_name": f"APPA_{i}"} for i in range(programados)])\n'
    content = content.replace(block, clean_block + "    ")

# Fix ITAQUI
match_itaqui = re.search(r'(linhas\.extend\(\[\{"port_id": "BRIQI".*?)except', content, re.DOTALL)
if match_itaqui:
    block = match_itaqui.group(1)
    clean_block = ""
    clean_block += '            linhas.extend([{"port_id": "BRIQI", "source": "emar_itaqui", "status": "atracado", "ship_name": f"ITAQUI_{i}"} for i in range(atracados)])\n'
    clean_block += '            linhas.extend([{"port_id": "BRIQI", "source": "emar_itaqui", "status": "ao_largo", "ship_name": f"ITAQUI_{i}"} for i in range(fundeados)])\n'
    clean_block += '            linhas.extend([{"port_id": "BRIQI", "source": "emar_itaqui", "status": "esperado", "ship_name": f"ITAQUI_{i}"} for i in range(esperados)])\n'
    content = content.replace(block, clean_block + "    ")

with open("src/ingestion/live_sources.py", "w") as f:
    f.write(content)
