import os
import sys
from datetime import datetime, timezone


# Garantir importação do projeto
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


import duckdb
from dotenv import load_dotenv


load_dotenv("config/.env")
DB_PATH = os.getenv("DATABASE_PATH", "data/oracle.duckdb")


PORTS = [
    {"port_id": "BRSSZ", "port_name": "Santos", "country": "Brasil", "congestion_score": 0.78, "eta_delay_days": 1.6, "waiting_vessels": 12, "freight_volatility_index": 0.42},
    {"port_id": "BRRIO", "port_name": "Rio de Janeiro", "country": "Brasil", "congestion_score": 0.45, "eta_delay_days": 0.9, "waiting_vessels": 5, "freight_volatility_index": 0.31},
    {"port_id": "CNSHA", "port_name": "Shanghai", "country": "China", "congestion_score": 0.72, "eta_delay_days": 1.5, "waiting_vessels": 18, "freight_volatility_index": 0.38},
    {"port_id": "CNNGB", "port_name": "Ningbo-Zhoushan", "country": "China", "congestion_score": 0.55, "eta_delay_days": 1.1, "waiting_vessels": 9, "freight_volatility_index": 0.35},
    {"port_id": "CNTAO", "port_name": "Qingdao", "country": "China", "congestion_score": 0.60, "eta_delay_days": 1.0, "waiting_vessels": 10, "freight_volatility_index": 0.41},
    {"port_id": "SGSIN", "port_name": "Singapore", "country": "Cingapura", "congestion_score": 0.62, "eta_delay_days": 1.2, "waiting_vessels": 14, "freight_volatility_index": 0.40},
    {"port_id": "NLRTM", "port_name": "Rotterdam", "country": "Holanda", "congestion_score": 0.40, "eta_delay_days": 0.8, "waiting_vessels": 6, "freight_volatility_index": 0.29},
    {"port_id": "USLAX", "port_name": "Los Angeles", "country": "EUA", "congestion_score": 0.58, "eta_delay_days": 1.1, "waiting_vessels": 10, "freight_volatility_index": 0.44},
    {"port_id": "USNYC", "port_name": "New York", "country": "EUA", "congestion_score": 0.34, "eta_delay_days": 0.6, "waiting_vessels": 4, "freight_volatility_index": 0.26},
    {"port_id": "DEHAM", "port_name": "Hamburg", "country": "Alemanha", "congestion_score": 0.44, "eta_delay_days": 0.9, "waiting_vessels": 7, "freight_volatility_index": 0.30},
    {"port_id": "MPTNG", "port_name": "Tanger Med", "country": "Marrocos", "congestion_score": 0.30, "eta_delay_days": 0.5, "waiting_vessels": 3, "freight_volatility_index": 0.22},
    {"port_id": "AEDXB", "port_name": "Dubai / Jebel Ali", "country": "EAU", "congestion_score": 0.50, "eta_delay_days": 1.0, "waiting_vessels": 8, "freight_volatility_index": 0.37},
    {"port_id": "KRPUS", "port_name": "Busan", "country": "Coreia do Sul", "congestion_score": 0.48, "eta_delay_days": 0.9, "waiting_vessels": 8, "freight_volatility_index": 0.33},
    {"port_id": "GBLGP", "port_name": "London Gateway", "country": "Reino Unido", "congestion_score": 0.37, "eta_delay_days": 0.7, "waiting_vessels": 4, "freight_volatility_index": 0.28},
    {"port_id": "ZACPT", "port_name": "Cape Town", "country": "África do Sul", "congestion_score": 0.66, "eta_delay_days": 1.4, "waiting_vessels": 11, "freight_volatility_index": 0.36},
    {"port_id": "MXZLO", "port_name": "Manzanillo", "country": "México", "congestion_score": 0.53, "eta_delay_days": 1.0, "waiting_vessels": 7, "freight_volatility_index": 0.39},
]


def seed_port_metrics():
    """Recria a tabela port_metrics e semeia o oráculo global com 16 portos estratégicos."""
    conn = duckdb.connect(DB_PATH)

    conn.execute("DROP TABLE IF EXISTS port_metrics")
    conn.execute("""
        CREATE TABLE port_metrics (
            port_id VARCHAR PRIMARY KEY,
            port_name VARCHAR,
            country VARCHAR,
            congestion_score DOUBLE,
            eta_delay_days DOUBLE,
            waiting_vessels INTEGER,
            freight_volatility_index DOUBLE,
            updated_at TIMESTAMP
        )
    """)

    updated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    conn.executemany(
        """
        INSERT INTO port_metrics (
            port_id, port_name, country, congestion_score,
            eta_delay_days, waiting_vessels, freight_volatility_index, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                p["port_id"], p["port_name"], p["country"], p["congestion_score"],
                p["eta_delay_days"], p["waiting_vessels"], p["freight_volatility_index"],
                updated_at
            )
            for p in PORTS
        ]
    )

    count = conn.execute("SELECT COUNT(*) FROM port_metrics").fetchone()[0]
    sample = conn.execute(
        "SELECT port_id, port_name FROM port_metrics ORDER BY port_id LIMIT 3"
    ).fetchall()
    conn.close()

    print(f"[AETHER-X PROD INIT] Oráculo semeado com sucesso em: {DB_PATH}")
    print(f"[AETHER-X PROD INIT] Total de portos na tabela port_metrics: {count}")
    print(f"[AETHER-X PROD INIT] Amostra: {sample}")


if __name__ == "__main__":
    print("[AETHER-X PROD INIT] Inicializando e semeando o banco DuckDB para produção...")
    seed_port_metrics()
    print("[AETHER-X PROD INIT] Banco semeado com sucesso!")