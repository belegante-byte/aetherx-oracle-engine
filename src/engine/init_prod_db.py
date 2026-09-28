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
    # ── Brasil ──
    {"port_id": "BRSSZ", "port_name": "Santos", "country": "Brasil", "congestion_score": 0.78, "eta_delay_days": 1.6, "waiting_vessels": 12, "freight_volatility_index": 0.42},
    {"port_id": "BRPNG", "port_name": "Paranaguá", "country": "Brasil", "congestion_score": 0.60, "eta_delay_days": 1.1, "waiting_vessels": 8, "freight_volatility_index": 0.36},
    {"port_id": "BRRIO", "port_name": "Rio de Janeiro", "country": "Brasil", "congestion_score": 0.45, "eta_delay_days": 0.9, "waiting_vessels": 5, "freight_volatility_index": 0.31},
    {"port_id": "BRNIT", "port_name": "Niterói", "country": "Brasil", "congestion_score": 0.38, "eta_delay_days": 0.7, "waiting_vessels": 3, "freight_volatility_index": 0.27},
    {"port_id": "BRITG", "port_name": "Itaguaí", "country": "Brasil", "congestion_score": 0.40, "eta_delay_days": 0.8, "waiting_vessels": 4, "freight_volatility_index": 0.29},
    {"port_id": "BRRGD", "port_name": "Rio Grande", "country": "Brasil", "congestion_score": 0.55, "eta_delay_days": 1.2, "waiting_vessels": 7, "freight_volatility_index": 0.34},
    {"port_id": "BRVDC", "port_name": "Barcarena / Vila do Conde", "country": "Brasil", "congestion_score": 0.62, "eta_delay_days": 1.4, "waiting_vessels": 9, "freight_volatility_index": 0.38},
    {"port_id": "BRMAO", "port_name": "Itaqui / São Luís", "country": "Brasil", "congestion_score": 0.58, "eta_delay_days": 1.3, "waiting_vessels": 8, "freight_volatility_index": 0.35},
    # ── Argentina ──
    {"port_id": "ARROS", "port_name": "Rosario / San Lorenzo", "country": "Argentina", "congestion_score": 0.68, "eta_delay_days": 1.5, "waiting_vessels": 14, "freight_volatility_index": 0.41},
    {"port_id": "ARBUE", "port_name": "Buenos Aires", "country": "Argentina", "congestion_score": 0.42, "eta_delay_days": 0.8, "waiting_vessels": 5, "freight_volatility_index": 0.28},
    # ── China & Ásia ──
    {"port_id": "CNSHA", "port_name": "Shanghai", "country": "China", "congestion_score": 0.72, "eta_delay_days": 1.5, "waiting_vessels": 18, "freight_volatility_index": 0.38},
    {"port_id": "CNNGB", "port_name": "Ningbo-Zhoushan", "country": "China", "congestion_score": 0.55, "eta_delay_days": 1.1, "waiting_vessels": 9, "freight_volatility_index": 0.35},
    {"port_id": "CNTAO", "port_name": "Qingdao", "country": "China", "congestion_score": 0.60, "eta_delay_days": 1.0, "waiting_vessels": 10, "freight_volatility_index": 0.41},
    {"port_id": "CNTXG", "port_name": "Tianjin", "country": "China", "congestion_score": 0.52, "eta_delay_days": 1.0, "waiting_vessels": 8, "freight_volatility_index": 0.33},
    {"port_id": "CNSZX", "port_name": "Shenzhen / Yantian", "country": "China", "congestion_score": 0.58, "eta_delay_days": 1.2, "waiting_vessels": 11, "freight_volatility_index": 0.36},
    {"port_id": "SGSIN", "port_name": "Singapore", "country": "Cingapura", "congestion_score": 0.62, "eta_delay_days": 1.2, "waiting_vessels": 14, "freight_volatility_index": 0.40},
    {"port_id": "KRPUS", "port_name": "Busan", "country": "Coreia do Sul", "congestion_score": 0.48, "eta_delay_days": 0.9, "waiting_vessels": 8, "freight_volatility_index": 0.33},
    {"port_id": "JPTYO", "port_name": "Tokyo / Yokohama", "country": "Japão", "congestion_score": 0.36, "eta_delay_days": 0.7, "waiting_vessels": 4, "freight_volatility_index": 0.25},
    # ── América do Norte ──
    {"port_id": "USMSY", "port_name": "New Orleans / Mississippi", "country": "EUA", "congestion_score": 0.64, "eta_delay_days": 1.4, "waiting_vessels": 12, "freight_volatility_index": 0.43},
    {"port_id": "USHOU", "port_name": "Houston", "country": "EUA", "congestion_score": 0.50, "eta_delay_days": 1.0, "waiting_vessels": 8, "freight_volatility_index": 0.32},
    {"port_id": "USLAX", "port_name": "Los Angeles", "country": "EUA", "congestion_score": 0.58, "eta_delay_days": 1.1, "waiting_vessels": 10, "freight_volatility_index": 0.44},
    {"port_id": "USNYC", "port_name": "New York", "country": "EUA", "congestion_score": 0.34, "eta_delay_days": 0.6, "waiting_vessels": 4, "freight_volatility_index": 0.26},
    {"port_id": "USSEA", "port_name": "Seattle / Tacoma", "country": "EUA", "congestion_score": 0.46, "eta_delay_days": 0.9, "waiting_vessels": 6, "freight_volatility_index": 0.30},
    {"port_id": "CAVAN", "port_name": "Vancouver", "country": "Canadá", "congestion_score": 0.57, "eta_delay_days": 1.2, "waiting_vessels": 9, "freight_volatility_index": 0.37},
    # ── Europa & Oriente Médio ──
    {"port_id": "NLRTM", "port_name": "Rotterdam", "country": "Holanda", "congestion_score": 0.40, "eta_delay_days": 0.8, "waiting_vessels": 6, "freight_volatility_index": 0.29},
    {"port_id": "DEHAM", "port_name": "Hamburg", "country": "Alemanha", "congestion_score": 0.44, "eta_delay_days": 0.9, "waiting_vessels": 7, "freight_volatility_index": 0.30},
    {"port_id": "BEANT", "port_name": "Antwerp", "country": "Bélgica", "congestion_score": 0.41, "eta_delay_days": 0.8, "waiting_vessels": 6, "freight_volatility_index": 0.28},
    {"port_id": "GBLGP", "port_name": "London Gateway", "country": "Reino Unido", "congestion_score": 0.37, "eta_delay_days": 0.7, "waiting_vessels": 4, "freight_volatility_index": 0.28},
    {"port_id": "MPTNG", "port_name": "Tanger Med", "country": "Marrocos", "congestion_score": 0.30, "eta_delay_days": 0.5, "waiting_vessels": 3, "freight_volatility_index": 0.22},
    {"port_id": "AEDXB", "port_name": "Dubai / Jebel Ali", "country": "EAU", "congestion_score": 0.50, "eta_delay_days": 1.0, "waiting_vessels": 8, "freight_volatility_index": 0.37},
    {"port_id": "SARAN", "port_name": "Ras Tanura", "country": "Arábia Saudita", "congestion_score": 0.45, "eta_delay_days": 0.9, "waiting_vessels": 7, "freight_volatility_index": 0.31},
    # ── Gargalos Globais (Canais) & África/LatAm ──
    {"port_id": "PABLB", "port_name": "Canal do Panamá / Balboa", "country": "Panamá", "congestion_score": 0.75, "eta_delay_days": 2.2, "waiting_vessels": 25, "freight_volatility_index": 0.52},
    {"port_id": "EGSUZ", "port_name": "Canal de Suez / Port Said", "country": "Egito", "congestion_score": 0.70, "eta_delay_days": 1.8, "waiting_vessels": 20, "freight_volatility_index": 0.48},
    {"port_id": "ZACPT", "port_name": "Cape Town", "country": "África do Sul", "congestion_score": 0.66, "eta_delay_days": 1.4, "waiting_vessels": 11, "freight_volatility_index": 0.36},
    {"port_id": "MXZLO", "port_name": "Manzanillo", "country": "México", "congestion_score": 0.53, "eta_delay_days": 1.0, "waiting_vessels": 7, "freight_volatility_index": 0.39},
]


# Fontes "live" FABRICADAS da era 35/35 live (commit 397064b) — nunca foram
# feeds integrados. Qualquer linha rotulada com elas é referência estática
# vendida como telemetria viva: normalize para calibrated_reference_seed.
LEGACY_FAKE_LIVE = (
    "portinsight_ais", "portcast_live", "gateway_lines", "kuehne_nagel",
    "vesselapi", "hutchison_intermodal", "findtrain_rail", "straittraffic_imf",
    "seavantage_chokepoint", "hormuztracking", "tankermap", "datalastic_africa",
)


def _normalize_legacy_fake_live(conn) -> int:
    """Idempotente: reescreve labels live fabricados p/ referência calibrada.

    Os valores (score/fila) das linhas afetadas SÃO os do seed de referência;
    só o rótulo era mentira. Preserva observações realmente vivas
    (appa, santos, lachmann, portosrio_silog, shipinfo_ais).
    """
    cond = " OR ".join(f"data_source LIKE '%{s}%'" for s in LEGACY_FAKE_LIVE)
    fake = conn.execute(
        "SELECT COUNT(*) FROM port_metrics WHERE data_source LIKE 'live:%' AND (" + cond + ")"
    ).fetchone()[0]
    if not fake:
        return 0
    conn.execute(
        "UPDATE port_metrics "
        "SET data_source = 'calibrated_reference_seed', "
        "data_source_label = 'Calibrated reference seed (static model baseline, NOT live telemetry).', "
        "live_detail = NULL "
        "WHERE data_source LIKE 'live:%' AND (" + cond + ")"
    )
    hist = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_name = 'port_metrics_history'"
    ).fetchone()[0]
    if hist:
        conn.execute(
            "UPDATE port_metrics_history SET data_source = 'calibrated_reference_seed' "
            "WHERE data_source LIKE 'live:%' AND (" + cond + ")"
        )
    return fake


def seed_port_metrics(force: bool = False):
    """Garante schema e semeia o oráculo sem destruir observações vivas.

    MITIGAÇÃO (auditoria 2026-09-21): a versão anterior executava
    `DROP TABLE IF EXISTS port_metrics` a cada boot — qualquer deploy Railway
    (startCommand roda `init_prod_db`) apagava filas live/calibradas atualizadas
    pela ingestão horária. Agora: CREATE IF NOT EXISTS + seed de portos ausentes
    (ON CONFLICT DO NOTHING). `--force` só recalcula o seed estático sob demanda.
    """
    conn = duckdb.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS port_metrics (
            port_id VARCHAR PRIMARY KEY,
            port_name VARCHAR,
            country VARCHAR,
            congestion_score DOUBLE,
            eta_delay_days DOUBLE,
            waiting_vessels INTEGER,
            freight_volatility_index DOUBLE,
            updated_at TIMESTAMP,
            data_source VARCHAR,
            data_source_label VARCHAR,
            live_detail VARCHAR
        )
    """)

    if force:
        # Reset explícito (operador): volta ao seed estático puro.
        conn.execute("DELETE FROM port_metrics")

    updated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    conn.executemany(
        """
        INSERT INTO port_metrics (
            port_id, port_name, country, congestion_score,
            eta_delay_days, waiting_vessels, freight_volatility_index, updated_at,
            data_source, data_source_label, live_detail
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (port_id) DO NOTHING
        """,
        [
            (
                p["port_id"], p["port_name"], p["country"], p["congestion_score"],
                p["eta_delay_days"], p["waiting_vessels"], p["freight_volatility_index"],
                updated_at,
                "static_reference_seed",
                "Static reference seed (not live telemetry).",
                None
            )
            for p in PORTS
        ]
    )

    # Auditoria antifake: linhas 'live' fabricadas (era 35/35 live) viram
    # referência calibrada honesta — idempotente, roda a cada boot.
    normalizadas = _normalize_legacy_fake_live(conn)

    count = conn.execute("SELECT COUNT(*) FROM port_metrics").fetchone()[0]
    vivos = conn.execute(
        "SELECT COUNT(*) FROM port_metrics WHERE data_source LIKE 'live:%'"
    ).fetchone()[0]
    sample = conn.execute(
        "SELECT port_id, port_name FROM port_metrics ORDER BY port_id LIMIT 3"
    ).fetchall()
    conn.close()

    print(f"[AETHER-X PROD INIT] Oráculo garantido em: {DB_PATH}")
    print(f"[AETHER-X PROD INIT] Total de portos: {count} | sources live preservadas: {vivos}")
    if normalizadas:
        print(f"[AETHER-X PROD INIT] Fakes-live normalizados p/ conferência: {normalizadas}")
    print(f"[AETHER-X PROD INIT] Amostra: {sample}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Garante o schema do oráculo sem apagar dados vivos.")
    parser.add_argument("--force", action="store_true", help="Reseta para o seed estático (drop de observações).")
    args = parser.parse_args()
    print("[AETHER-X PROD INIT] Garantindo o banco DuckDB para produção (idempotente)...")
    seed_port_metrics(force=args.force)
    print("[AETHER-X PROD INIT] Banco pronto.")