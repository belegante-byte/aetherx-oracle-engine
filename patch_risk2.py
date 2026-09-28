with open("src/engine/risk_model.py", "r") as f:
    content = f.read()

signal_logic = """
    # Enriquecimento padrao (signal e decision_grade)
    is_live = result.get("data_source", "").startswith("live:")
    score = result.get("congestion_score", 0.5)
    result["decision_grade"] = "conditional" if is_live else "reference"
    
    if result.get("signal") is None:
        result["signal"] = {
            "level": "ELEVATED OPERATIONAL PRESSURE" if score >= 0.45 else "MODERATE / LOW PRESSURE",
            "live_observation": is_live,
            "queue_vessels": result.get("waiting_vessels", 0),
            "expected_delay_days": result.get("eta_delay_days", 0),
            "demurrage_expected_usd": int(result.get("eta_delay_days", 0) * DEMURRAGE_BASE_USD_PER_DAY),
            "confidence": 0.94 if is_live else None,
            "provenance": result.get("data_source"),
            "decision_implication": f"{'Live stream' if is_live else 'Reference seed'} indicates operational pressure at {result['port_name']}.",
            "as_of": result.get("as_of")
        }

    return result
"""

content = content.replace("    return result\n", signal_logic)

with open("src/engine/risk_model.py", "w") as f:
    f.write(content)
print("Added signal logic back to risk_model.py")
