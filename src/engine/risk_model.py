import os
import duckdb
from datetime import datetime, timezone
from dotenv import load_dotenv


load_dotenv("config/.env")
DB_PATH = os.getenv("DATABASE_PATH", "data/oracle.duckdb")

# Estimativa fallback baseada em estatísticas globais genéricas de congestão portuária
GLOBAL_ESTIMATE = {
    "port_name": "Unknown Port (Global Estimate)",
    "country": "Global",
    "congestion_score": 0.45,
    "eta_delay_days": 1.0,
    "waiting_vessels": 6,
    "freight_volatility_index": 0.35,
}


def calculate_port_risk(port_id: str) -> dict:
    """
    Lê os dados reais do porto em port_metrics no DuckDB.
    Caso o porto não exista, retorna uma estimativa baseada em estatísticas globais.
    """
    port_id = port_id.upper()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    try:
        conn = duckdb.connect(DB_PATH)
        row = conn.execute("""
            SELECT port_id, port_name, country, congestion_score,
                   eta_delay_days, waiting_vessels, freight_volatility_index,
                   CAST(updated_at AS VARCHAR) AS updated_at
            FROM port_metrics
            WHERE port_id = ?
        """, [port_id]).fetchone()
        conn.close()
    except duckdb.Error:
        row = None

    if row is None:
        return {
            "port_id": port_id,
            "port_name": GLOBAL_ESTIMATE["port_name"],
            "country": GLOBAL_ESTIMATE["country"],
            "congestion_score": GLOBAL_ESTIMATE["congestion_score"],
            "eta_delay_days": GLOBAL_ESTIMATE["eta_delay_days"],
            "waiting_vessels": GLOBAL_ESTIMATE["waiting_vessels"],
            "freight_volatility_index": GLOBAL_ESTIMATE["freight_volatility_index"],
            "updated_at": now,
        }

    return {
        "port_id": row[0],
        "port_name": row[1],
        "country": row[2],
        "congestion_score": row[3],
        "eta_delay_days": row[4],
        "waiting_vessels": row[5],
        "freight_volatility_index": row[6],
        "updated_at": row[7],
    }