import re

with open("src/ingestion/live_sources.py", "r") as f:
    content = f.read()

# Replace all instances of `linhas.extend([{"port_id": "BRPNG", "status": "atracado", "ship_name": f"ITAQUI_{i}"} for i in range(atracados)])`
# with BRIQI
content = content.replace('"port_id": "BRPNG", "status": "atracado", "ship_name": f"ITAQUI_', '"port_id": "BRIQI", "status": "atracado", "ship_name": f"ITAQUI_')
content = content.replace('"port_id": "BRPNG", "status": "ao_largo", "ship_name": f"ITAQUI_', '"port_id": "BRIQI", "status": "ao_largo", "ship_name": f"ITAQUI_')
content = content.replace('"port_id": "BRPNG", "status": "esperado", "ship_name": f"ITAQUI_', '"port_id": "BRIQI", "status": "esperado", "ship_name": f"ITAQUI_')

with open("src/ingestion/live_sources.py", "w") as f:
    f.write(content)
