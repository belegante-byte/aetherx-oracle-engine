import re

with open("src/engine/risk_model.py", "r") as f:
    content = f.read()

new_trend_func = """
@functools.lru_cache(maxsize=1024)
def calculate_port_trend(port_id: str, horizons: tuple = TREND_HORIZONS) -> dict:
    \"\"\"Projeta o congestionamento do porto para os próximos horizontes (24/48/72h)
    usando regressão linear local (Numpy) sobre o histórico real (DuckDB).
    \"\"\"
    import numpy as np
    
    base = calculate_port_risk(port_id)
    score = base["congestion_score"]
    
    # Busca histórico das últimas 168 horas (7 dias)
    conn = _get_conn()
    history = conn.execute(
        \"\"\"
        SELECT captured_at, congestion_score
        FROM port_metrics_history
        WHERE port_id = ?
          AND captured_at >= current_timestamp - interval '7 days'
        ORDER BY captured_at ASC
        \"\"\",
        [port_id]
    ).fetchall()
    
    projection = {}
    
    if len(history) < 3:
        # Fallback se não houver histórico suficiente (ex: seed recente)
        target = score
        for h in horizons:
            projection[f"h{h}"] = {
                "congestion_score": score,
                "eta_delay_days": base["eta_delay_days"],
                "estimated_daily_demurrage_usd": _estimate_demurrage(score),
            }
        trend_label = "estável"
        final_score = score
    else:
        # Converte para horas relativas (0 = mais antigo do período)
        import datetime
        times = [r[0] for r in history]
        scores = [r[1] for r in history]
        
        t0 = times[-1] # current time
        x = np.array([(t - t0).total_seconds() / 3600.0 for t in times])
        y = np.array(scores)
        
        # Regressão linear simples: y = mx + c
        m, c = np.polyfit(x, y, 1)
        
        # Previsão
        for h in horizons:
            pred_score = m * h + c
            # Limita entre 0.05 e 0.95
            s = round(max(0.05, min(0.95, float(pred_score))), 2)
            ratio = (s / score) if score else 1.0
            projection[f"h{h}"] = {
                "congestion_score": s,
                "eta_delay_days": round(base["eta_delay_days"] * ratio, 2),
                "estimated_daily_demurrage_usd": _estimate_demurrage(s),
            }
        
        final_score = projection[f"h{horizons[-1]}"]["congestion_score"]
        delta = final_score - score
        trend_label = _trend_label(delta)

    return {
        "port_id": base["port_id"],
        "port_name": base["port_name"],
        "country": base["country"],
        "trend": trend_label,
        "congestion_score": score,
        "projection": projection,
        "updated_at": base["updated_at"],
        "as_of": base["as_of"],
        "data_source": "predictive_ml_regression",
        "data_source_label": "Local ML Regression (Numpy) trained on historical telemetry.",
    }
"""

# Usar regex para substituir a função existente
content = re.sub(
    r"@functools\.lru_cache\(maxsize=1024\)\ndef calculate_port_trend\(.*?return \{.*?\n    \}",
    new_trend_func.strip(),
    content,
    flags=re.DOTALL
)

with open("src/engine/risk_model.py", "w") as f:
    f.write(content)

print("Patch applied.")
