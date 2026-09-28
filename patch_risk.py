import re

with open("src/engine/risk_model.py", "r") as f:
    content = f.read()

# We need to remove the whole try block that imports fetch_* and overrides DB
# Looking for "try:\n        from src.ingestion.live_sources import fetch_"
pattern = r"    # Enriquecimento com referência calibrada para portos asiáticos.*?return result"

# Let's just find the exact block and replace it with "return result"
# We will use string split and replace
# It starts at "# Enriquecimento com referência calibrada para portos asiáticos"
idx1 = content.find("    # Enriquecimento com referência calibrada")
idx2 = content.find("    return result", idx1)

if idx1 != -1 and idx2 != -1:
    content = content[:idx1] + "    return result\n" + content[idx2 + len("    return result\n"):]
    with open("src/engine/risk_model.py", "w") as f:
        f.write(content)
    print("Risk model patched successfully!")
else:
    print("Could not find block")
