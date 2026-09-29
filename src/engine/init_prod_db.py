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
    {"port_id": "NLAMS", "port_name": "Amsterdam", "country": "Holanda", "congestion_score": 0.38, "eta_delay_days": 0.6, "waiting_vessels": 4, "freight_volatility_index": 0.25},
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


    conn.execute('''
        CREATE TABLE IF NOT EXISTS port_metrics_history(
            captured_at TIMESTAMP,
            port_id VARCHAR, 
            port_name VARCHAR, 
            country VARCHAR, 
            congestion_score DOUBLE, 
            eta_delay_days DOUBLE, 
            waiting_vessels INTEGER, 
            freight_volatility_index DOUBLE, 
            estimated_daily_demurrage_usd INTEGER, 
            data_source VARCHAR, 
            as_of VARCHAR
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS m2m_keys(
            client_id VARCHAR PRIMARY KEY,
            owner_name VARCHAR,
            plan VARCHAR,
            is_active BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tax_rules (
            state_code VARCHAR,
            commodity VARCHAR,
            icms_rate_pct DOUBLE,
            exemption_note VARCHAR,
            PRIMARY KEY (state_code, commodity)
        )
    """)

    conn.executemany(
        """
        INSERT INTO tax_rules (state_code, commodity, icms_rate_pct, exemption_note)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (state_code, commodity) DO UPDATE SET
            icms_rate_pct = EXCLUDED.icms_rate_pct,
            exemption_note = EXCLUDED.exemption_note
        """,
        [
            ("SP", "SOJA", 18.0, None),
            ("SP", "FERTILIZANTES", 18.0, None),
            ("PR", "SOJA", 12.0, None),
            ("PR", "FERTILIZANTES", 0.0, "Isento - Convênio ICMS 100/97"),
            ("MA", "SOJA", 12.0, None),
            ("MA", "FERTILIZANTES", 12.0, None),
            ("RJ", "SOJA", 20.0, None),
            ("RJ", "FERTILIZANTES", 20.0, None),
            ("RS", "SOJA", 17.0, None),
            ("RS", "FERTILIZANTES", 17.0, None),
            ("MT", "SOJA", 12.0, None),
            ("MT", "FERTILIZANTES", 0.0, "Isento - Convênio ICMS 100/97 (Destino)"),
            ("GO", "SOJA", 12.0, None),
            ("GO", "FERTILIZANTES", 0.0, "Isento - Convênio ICMS 100/97 (Destino)")
        ]
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS freight_rates (
            origin_uf VARCHAR,
            port_id VARCHAR,
            rate_brl_per_ton DOUBLE,
            mode VARCHAR,
            source VARCHAR,
            reference_date VARCHAR,
            is_estimate BOOLEAN,
            PRIMARY KEY (origin_uf, port_id)
        )
    """)

    # FASE 2 (Fretes Reais): tarifas de corredores rodoviários de grãos em R$/t,
    # convertidas a USD/t em tempo de execução via USD_BRL_FX (default 5,22 —
    # dólar comercial 28/09/2026). Corredores publicados pela CONAB Boletim
    # Logístico (07/2026) e Sifreca/ESALQ-USP vêm com is_estimate=FALSE e fonte
    # citada; corredores sem tarifa publicada recebem estimativa calibrada e
    # explicitamente marcada (is_estimate=TRUE) — nada é vendido como "live" sem ser.
    _FREIGHT_ROWS = [
        # MT (praça Sorriso/Rondonópolis) — documentado pela CONAB 07/2026
        ("MT", "BRSSZ", 510.0, "rodoviário", "CONAB Boletim Logístico 07/2026 (Sorriso-Santos)", "2026-07", False),
        ("MT", "BRPNG", 500.0, "rodoviário", "CONAB Boletim Logístico 07/2026 (Sorriso-Paranaguá)", "2026-07", False),
        ("MT", "BRMAO", 400.0, "rodoviário", "Proxy Arco Norte (Santarém 420 / Itaituba 315, Sifreca) - sem rota própria publicada p/ Itaqui", "2026-07", True),
        ("MT", "BRRIO", 650.0, "rodoviário", "Estimativa Sifreca R$/t.km (sem corredor de grãos publicado MT-RJ)", "2026-07", True),
        ("MT", "BRRGD", 700.0, "rodoviário", "Estimativa Sifreca R$/t.km (sem corredor de grãos publicado MT-RS)", "2026-07", True),
        # GO (praça Rio Verde)
        ("GO", "BRSSZ", 350.0, "rodoviário", "CONAB Boletim Logístico 07/2026 (Rio Verde-Santos)", "2026-07", False),
        ("GO", "BRPNG", 300.0, "rodoviário", "CONAB Boletim Logístico (Rio Verde-Paranaguá)", "2026-07", False),
        ("GO", "BRMAO", 450.0, "rodoviário", "Estimativa Sifreca R$/t.km (sem rota publicada GO-Itaqui)", "2026-07", True),
        ("GO", "BRRIO", 400.0, "rodoviário", "Estimativa Sifreca R$/t.km (sem rota publicada GO-RJ)", "2026-07", True),
        ("GO", "BRRGD", 450.0, "rodoviário", "Estimativa Sifreca R$/t.km (sem rota publicada GO-RS)", "2026-07", True),
        # MS (praça Dourados/Chapadão) — CONAB reporta alta generalizada em MS
        ("MS", "BRSSZ", 300.0, "rodoviário", "CONAB Boletim Logístico 07/2026 (MS-Santos)", "2026-07", False),
        ("MS", "BRPNG", 280.0, "rodoviário", "CONAB Boletim Logístico 07/2026 (MS-Paranaguá)", "2026-07", False),
        ("MS", "BRRGD", 250.0, "rodoviário", "Estimativa Sifreca R$/t.km (sem rota publicada MS-Rio Grande)", "2026-07", True),
        ("MS", "BRMAO", 1000.0, "rodoviário", "Estimativa Sifreca R$/t.km (sem rota publicada MS-Itaqui)", "2026-07", True),
        ("MS", "BRRIO", 400.0, "rodoviário", "Estimativa Sifreca R$/t.km (sem rota publicada MS-RJ)", "2026-07", True),
        # PR (praça Londrina/Campo Mourão/Maringá)
        ("PR", "BRPNG", 190.0, "rodoviário", "CONAB Boletim Logístico 07/2026 (Campo Mourão-Paranaguá)", "2026-07", False),
        ("PR", "BRSSZ", 230.0, "rodoviário", "Estimativa Sifreca R$/t.km (PR-Santos)", "2026-07", True),
        ("PR", "BRRIO", 250.0, "rodoviário", "Estimativa Sifreca R$/t.km (PR-RJ)", "2026-07", True),
        ("PR", "BRRGD", 260.0, "rodoviário", "Estimativa Sifreca R$/t.km (PR-Rio Grande)", "2026-07", True),
        ("PR", "BRMAO", 1100.0, "rodoviário", "Estimativa Sifreca R$/t.km (sem rota publicada PR-Itaqui)", "2026-07", True),
        # SP (interior paulista)
        ("SP", "BRSSZ", 90.0, "rodoviário", "CONAB Boletim Logístico 07/2026 (praças SP estáveis, interior-Santos)", "2026-07", False),
        ("SP", "BRRIO", 150.0, "rodoviário", "Estimativa Sifreca R$/t.km (interior SP-RJ)", "2026-07", True),
        ("SP", "BRPNG", 200.0, "rodoviário", "Estimativa Sifreca R$/t.km (SP-Paranaguá)", "2026-07", True),
        ("SP", "BRRGD", 400.0, "rodoviário", "Estimativa Sifreca R$/t.km (SP-Rio Grande)", "2026-07", True),
        ("SP", "BRMAO", 1200.0, "rodoviário", "Estimativa Sifreca R$/t.km (sem rota publicada SP-Itaqui)", "2026-07", True),
        # MG (praça Uberaba/Araguari)
        ("MG", "BRSSZ", 200.0, "rodoviário", "CONAB Boletim Logístico 07/2026 (MG-Santos)", "2026-07", False),
        ("MG", "BRRIO", 140.0, "rodoviário", "Estimativa Sifreca R$/t.km (MG-RJ)", "2026-07", True),
        ("MG", "BRPNG", 260.0, "rodoviário", "Estimativa Sifreca R$/t.km (MG-Paranaguá)", "2026-07", True),
        ("MG", "BRRGD", 300.0, "rodoviário", "Estimativa Sifreca R$/t.km (MG-Rio Grande)", "2026-07", True),
        ("MG", "BRMAO", 1100.0, "rodoviário", "Estimativa Sifreca R$/t.km (sem rota publicada MG-Itaqui)", "2026-07", True),
        # RS (praça Porto Alegre/Pelotas)
        ("RS", "BRRGD", 60.0, "rodoviário", "CONAB Boletim Logístico 07/2026 (RS-Rio Grande)", "2026-07", False),
        ("RS", "BRPNG", 180.0, "rodoviário", "Estimativa Sifreca R$/t.km (RS-Paranaguá)", "2026-07", True),
        ("RS", "BRSSZ", 220.0, "rodoviário", "Estimativa Sifreca R$/t.km (RS-Santos)", "2026-07", True),
        ("RS", "BRRIO", 250.0, "rodoviário", "Estimativa Sifreca R$/t.km (RS-RJ)", "2026-07", True),
        ("RS", "BRMAO", 1300.0, "rodoviário", "Estimativa Sifreca R$/t.km (sem rota publicada RS-Itaqui)", "2026-07", True),
    ]
    conn.executemany(
        """
        INSERT INTO freight_rates (origin_uf, port_id, rate_brl_per_ton, mode, source, reference_date, is_estimate)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (origin_uf, port_id) DO UPDATE SET
            rate_brl_per_ton = EXCLUDED.rate_brl_per_ton,
            mode = EXCLUDED.mode,
            source = EXCLUDED.source,
            reference_date = EXCLUDED.reference_date,
            is_estimate = EXCLUDED.is_estimate
        """,
        _FREIGHT_ROWS,
    )

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

    # Hidratação do seed curado (2026-09-29): `data/` é VOLUME no Railway e
    # sombreia o `data/` da imagem, então prod nascia sem antaq_validation /
    # calibration_pairs. A hidratação é ADITIVA e idempotente (nunca drop/update
    # de observação, nunca ressuscita sensor morto). Ver src/engine/seed_hydration.py.
    seed_report = {}
    try:
        from src.engine.seed_hydration import hydrate_from_seed
        seed_report = hydrate_from_seed(conn)
    except Exception as exc:  # pragma: no cover - bootstrap nunca deve morrer por isso
        seed_report = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

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
    if seed_report:
        print(
            "[AETHER-X PROD INIT] Seed: status={status} inseridos={ins} "
            "colunas_add={cols} live_bloqueados={live}".format(
                status=seed_report.get("status"),
                ins=seed_report.get("inserted"),
                cols=seed_report.get("added_columns") or "-",
                live=seed_report.get("live_rows_blocked") or "-",
            )
        )
    print(f"[AETHER-X PROD INIT] Amostra: {sample}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Garante o schema do oráculo sem apagar dados vivos.")
    parser.add_argument("--force", action="store_true", help="Reseta para o seed estático (drop de observações).")
    args = parser.parse_args()
    print("[AETHER-X PROD INIT] Garantindo o banco DuckDB para produção (idempotente)...")
    seed_port_metrics(force=args.force)
    print("[AETHER-X PROD INIT] Banco pronto.")