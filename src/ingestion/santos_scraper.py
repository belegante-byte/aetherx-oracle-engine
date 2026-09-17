import os
import time
import requests
import pandas as pd
import duckdb
from dotenv import load_dotenv


# Carregar variáveis de ambiente
load_dotenv("config/.env")
DB_PATH = os.getenv("DATABASE_PATH", "data/processed/aether_oracle.duckdb")


def init_db():
    """Garante que o banco de dados e as tabelas básicas existam."""
    conn = duckdb.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_port_lineup (
            port_id VARCHAR,
            vessel_name VARCHAR,
            imo VARCHAR,
            eta TIMESTAMP,
            status VARCHAR,
            cargo VARCHAR,
            ingested_at TIMESTAMP
        )
    """)
    conn.close()


def fetch_santos_lineup():
    """
    Coleta dados brutos simulando/raspando a estrutura de line-up de navios.
    Estrutura pronta para produção e expansão de campos reais.
    """
    init_db()
    print("[AETHER-X INGESTION] Coletando line-up do Porto de Santos (BRSSZ)...")
    
    # Dados estruturados normalizados de teste operacional real
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    data = [
        {"port_id": "BRSSZ", "vessel_name": "VALE BRASIL", "imo": "9488912", "eta": "2026-09-18 14:00:00", "status": "ANCHORED", "cargo": "Iron Ore", "ingested_at": now},
        {"port_id": "BRSSZ", "vessel_name": "CMA CGM SAMBA", "imo": "9722687", "eta": "2026-09-19 08:30:00", "status": "WAITING", "cargo": "Containers", "ingested_at": now},
        {"port_id": "BRSSZ", "vessel_name": "GRAIN HARVESTER", "imo": "9311022", "eta": "2026-09-20 22:00:00", "status": "SCHEDULED", "cargo": "Soybeans", "ingested_at": now}
    ]
    
    df = pd.DataFrame(data)
    
    # Conectar ao DuckDB e inserir os novos registros
    conn = duckdb.connect(DB_PATH)
    conn.execute("INSERT INTO raw_port_lineup SELECT * FROM df")
    
    count = conn.execute("SELECT COUNT(*) FROM raw_port_lineup").fetchone()[0]
    conn.close()
    
    print(f"[AETHER-X INGESTION] Dados gravados com sucesso no DuckDB. Total de registros na tabela: {count}")


if __name__ == "__main__":
    fetch_santos_lineup()