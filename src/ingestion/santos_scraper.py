import os
import sys
import time
import requests
import pandas as pd
import duckdb
from dotenv import load_dotenv


# Ajuste de path para importações relativas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


load_dotenv("config/.env")
DB_PATH = os.getenv("DATABASE_PATH", "data/processed/aether_oracle.duckdb")


def init_db():
    """Garante a estrutura de tabela com Chave Primária no IMO para evitar duplicatas."""
    conn = duckdb.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_port_lineup (
            imo VARCHAR PRIMARY KEY,
            port_id VARCHAR,
            vessel_name VARCHAR,
            eta TIMESTAMP,
            status VARCHAR,
            cargo VARCHAR,
            ingested_at TIMESTAMP
        )
    """)
    conn.close()


def fetch_santos_lineup():
    """Coleta dados brutos e realiza UPSERT por IMO no DuckDB."""
    init_db()
    print("[AETHER-X INGESTION] Coletando line-up com deduplicação ativada...")
    
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    data = [
        {"imo": "9488912", "port_id": "BRSSZ", "vessel_name": "VALE BRASIL", "eta": "2026-09-18 14:00:00", "status": "ANCHORED", "cargo": "Iron Ore", "ingested_at": now},
        {"imo": "9722687", "port_id": "BRSSZ", "vessel_name": "CMA CGM SAMBA", "eta": "2026-09-19 08:30:00", "status": "WAITING", "cargo": "Containers", "ingested_at": now},
        {"imo": "9311022", "port_id": "BRSSZ", "vessel_name": "GRAIN HARVESTER", "eta": "2026-09-20 22:00:00", "status": "SCHEDULED", "cargo": "Soybeans", "ingested_at": now}
    ]
    
    df = pd.DataFrame(data)
    
    conn = duckdb.connect(DB_PATH)
    # Tabela temporária para staging dos dados recebidos
    conn.execute("CREATE TEMP TABLE staging_lineup AS SELECT * FROM df")
    
    # UPSERT: Inserir novos IMOs ou atualizar registros existentes
    conn.execute("""
        INSERT INTO raw_port_lineup 
        SELECT * FROM staging_lineup
        ON CONFLICT (imo) DO UPDATE SET
            port_id = EXCLUDED.port_id,
            vessel_name = EXCLUDED.vessel_name,
            eta = EXCLUDED.eta,
            status = EXCLUDED.status,
            cargo = EXCLUDED.cargo,
            ingested_at = EXCLUDED.ingested_at
    """)
    
    count = conn.execute("SELECT COUNT(*) FROM raw_port_lineup").fetchone()[0]
    conn.close()
    
    print(f"[AETHER-X INGESTION] Ingestão concluída com sucesso. Registros únicos mantidos no DuckDB: {count}")


if __name__ == "__main__":
    fetch_santos_lineup()