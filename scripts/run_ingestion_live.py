"""Script de ingestão viva: fontes reais do GP5 -> DuckDB (raw + port_metrics).

Quando dados vivos existem para um porto BR (BRPNG/BRSSZ), as métricas de
congestão são DERIVADAS dos line-ups reais (navios ao largo, esperados,
atracados). Para portos sem fonte viva, mantém-se o seed de referência com
data_source=static_reference_seed (honesto).

Fontes vivas:
- APPA Paranaguá: line-up ao vivo com status (ao_largo = fila real).
- Santos: atracações programadas + painel de operações.
- Lachmann: ETAs reais de serviços de Paranaguá.

Uso:  python -m scripts.run_ingestion_live   (ou via __main__ abaixo)
"""

import os
import sys
import json
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import duckdb
from dotenv import load_dotenv

from src.ingestion.live_sources import (
    coletar_tudo,
    resumo_por_porto,
    TO_STATUS,
    SOURCE_LABELS,
    fetch_asian_port_congestion,
    fetch_european_port_congestion,
    fetch_americas_port_congestion,
    fetch_chokepoint_and_african_telemetry,
)
from src.ingestion.land_sources import fetch_rumo_operations
from src.engine.init_prod_db import PORTS


load_dotenv("config/.env")
RAW_DB = os.getenv("RAW_DATABASE_PATH", "data/processed/aether_oracle.duckdb")
_raw_oracle_db = os.getenv("DATABASE_PATH", "data/oracle.duckdb")
ORACLE_DB = _raw_oracle_db if os.path.exists(_raw_oracle_db) else "data/oracle.duckdb"

# Port metadata mapping for all ports
PORT_META_MAP = {p["port_id"]: p for p in PORTS}

GRID = {
    "BRPNG": {"port_name": "Paranaguá", "country": "Brasil"},
    "BRSSZ": {"port_name": "Santos", "country": "Brasil"},
    "BRRIO": {"port_name": "Rio de Janeiro", "country": "Brasil"},
    "BRNIT": {"port_name": "Niterói", "country": "Brasil"},
    "BRITG": {"port_name": "Itaguaí", "country": "Brasil"},
}


def gravar_raw_land() -> int:
    land_data = fetch_rumo_operations(allow_mock=True)
    conn = duckdb.connect(RAW_DB)
    conn.execute("DROP TABLE IF EXISTS raw_land_queue")
    conn.execute("""
        CREATE TABLE raw_land_queue (
            train_id VARCHAR,
            port_id VARCHAR,
            terminal VARCHAR,
            commodity VARCHAR,
            wagons INTEGER,
            status VARCHAR,
            source VARCHAR,
            ingested_at TIMESTAMP
        )
    """)
    
    data = []
    for r in land_data:
        data.append((
            r.get("train_id"),
            r.get("port_id"),
            r.get("terminal"),
            r.get("commodity"),
            r.get("wagons", 0),
            r.get("status"),
            r.get("source"),
            r.get("ingested_at"),
        ))
        
    if data:
        conn.executemany(
            "INSERT INTO raw_land_queue VALUES (?, ?, ?, ?, ?, ?, ?, ?)", data
        )
    total = conn.execute("SELECT COUNT(*) FROM raw_land_queue").fetchone()[0]
    conn.close()
    return total


def gravar_raw(linhas: list) -> int:
    conn = duckdb.connect(RAW_DB)
    conn.execute("DROP TABLE IF EXISTS raw_port_lineup")
    conn.execute("""
        CREATE TABLE raw_port_lineup (
            imo VARCHAR,
            port_id VARCHAR,
            vessel_name VARCHAR,
            eta VARCHAR,
            status VARCHAR,
            cargo VARCHAR,
            agency VARCHAR,
            source VARCHAR,
            dwt DOUBLE,
            ingested_at TIMESTAMP
        )
    """)
    data = []
    for r in linhas:
        data.append((
            r.get("imo"),
            r.get("port_id"),
            r.get("vessel_name"),
            r.get("eta"),
            TO_STATUS.get(r.get("status", ""), str(r.get("status", "")).upper()),
            r.get("cargo"),
            r.get("agency"),
            r.get("source"),
            r.get("dwt", 0.0),
            r.get("ingested_at"),
        ))
    if data:
        conn.executemany(
            "INSERT INTO raw_port_lineup VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", data
        )
    total = conn.execute("SELECT COUNT(*) FROM raw_port_lineup").fetchone()[0]
    conn.close()
    return total


def _score_from_status(pid: str, resumo: dict, fonte: dict) -> dict:
    status_keys = {k: v for k, v in resumo.items() if k.startswith("status_")}
    atracados = status_keys.get("status_ATRACADO", 0) + status_keys.get("status_EM_OPERACAO", 0)
    ao_largo = status_keys.get("status_AO_LARGO", 0)
    esperados = status_keys.get("status_ESPERADO", 0)
    programados = status_keys.get("status_PROGRAMADO", 0)

    waiting = ao_largo
    berçado = max(atracados, 1)

    razao = waiting / berçado
    score = 0.25 + 0.35 * min(razao, 2.0)
    score = max(0.05, min(0.97, score))

    if waiting == 0:
        eta_delay = 0.2
    elif waiting < 10:
        eta_delay = round(0.5 + waiting * 0.08, 2)
    elif waiting < 40:
        eta_delay = round(1.2 + waiting * 0.04, 2)
    else:
        eta_delay = round(2.4 + waiting * 0.02, 2)

    cargas = {k: v for k, v in resumo.items() if k.startswith("src_")}
    frete = 0.28 + 0.06 * min(len(cargas), 3) + 0.04 * min(ao_largo, 10)
    frete = max(0.20, min(0.85, round(frete, 2)))

    return {
        "congestion_score": round(score, 3),
        "waiting_vessels": int(waiting),
        "eta_delay_days": eta_delay,
        "freight_volatility_index": frete,
        "ao_largo": int(ao_largo),
        "esperados": int(esperados),
        "atracados": int(atracados),
        "programados": int(programados),
    }


def aplicar_no_oracle(por_porto: dict, resumos: dict | None = None) -> dict:
    from src.engine.risk_model import close_conn
    close_conn()
    conn = duckdb.connect(ORACLE_DB)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    atualizados = {}
    for pid, met in por_porto.items():
        meta = PORT_META_MAP.get(pid) or GRID.get(pid) or {
            "port_name": met.get("port_name", pid),
            "country": met.get("country", "Global"),
        }
        live_detail = met.get("live_detail_str")
        if not live_detail and "ao_largo" in met:
            live_detail = json.dumps({
                "ao_largo": met["ao_largo"],
                "esperados": met["esperados"],
                "atracados": met["atracados"],
                "programados": met["programados"],
            }, ensure_ascii=False)
        elif not live_detail:
            live_detail = json.dumps({
                "waiting_vessels": met.get("waiting_vessels", 0),
                "eta_delay_days": met.get("eta_delay_days", 0.0),
                "sources": met.get("sources_list", []),
            }, ensure_ascii=False)

        conn.execute("""
            INSERT INTO port_metrics (
                port_id, port_name, country, congestion_score,
                eta_delay_days, waiting_vessels, freight_volatility_index, updated_at,
                data_source, data_source_label, live_detail
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (port_id) DO UPDATE SET
                port_name = EXCLUDED.port_name,
                country = EXCLUDED.country,
                congestion_score = EXCLUDED.congestion_score,
                eta_delay_days = EXCLUDED.eta_delay_days,
                waiting_vessels = EXCLUDED.waiting_vessels,
                freight_volatility_index = EXCLUDED.freight_volatility_index,
                updated_at = EXCLUDED.updated_at,
                data_source = EXCLUDED.data_source,
                data_source_label = EXCLUDED.data_source_label,
                live_detail = EXCLUDED.live_detail
        """, (
            pid, meta["port_name"], meta["country"],
            met["congestion_score"], met["eta_delay_days"],
            met["waiting_vessels"], met.get("freight_volatility_index", 0.35), now,
            met["data_source"], met["data_source_label"],
            live_detail
        ))
        atualizados[pid] = met
    conn.close()
    return atualizados


def main() -> dict:
    print("== Aether-X: ingestão de fontes vivas ==")
    resultado = coletar_tudo()
    linhas = resultado.get("linhas", [])
    fontes_status = resultado.get("fontes", {})
    resumos = resumo_por_porto(linhas)

    print(f"Coletadas {len(linhas)} linhas reais. Fontes: {json.dumps(fontes_status)}")

    # 1. Deriva métricas para portos BR com line-up vivo
    por_porto = {}
    for pid, meta in GRID.items():
        resumo = resumos.get(pid)
        if not resumo or resumo.get("total", 0) == 0:
            continue
        met = _score_from_status(pid, resumo, fontes_status)
        fontes_usadas = sorted(
            k[4:] for k in resumo if k.startswith("src_")
        )
        met["data_source"] = "live:" + "+".join(fontes_usadas)
        nomes = [SOURCE_LABELS.get(f, f.replace("_", " ")) for f in fontes_usadas]
        met["data_source_label"] = (
            "Live line-up from " + " + ".join(nomes) + "."
        )
        por_porto[pid] = met

    # 2. Coleta telemetria viva multi-região (Ásia, Europa, Américas, África & Chokepoints)
    telemetry_sources = [
        fetch_asian_port_congestion(),
        fetch_european_port_congestion(),
        fetch_americas_port_congestion(),
        fetch_chokepoint_and_african_telemetry(),
    ]
    for source_dict in telemetry_sources:
        for pid, tdata in source_dict.items():
            src_keys = tdata.get("sources", [])
            src_str = "live:" + "+".join(src_keys) if src_keys else "live:telemetry"
            src_names = [SOURCE_LABELS.get(s, s.replace("_", " ")) for s in src_keys]
            src_label = "Live telemetry from " + " + ".join(src_names) + "." if src_names else "Live operational telemetry."
            por_porto[pid] = {
                "port_name": tdata.get("port_name", pid),
                "country": tdata.get("country", "Global"),
                "congestion_score": tdata.get("congestion_score", 0.5),
                "eta_delay_days": tdata.get("eta_delay_days", 1.0),
                "waiting_vessels": tdata.get("waiting_vessels", 10),
                "freight_volatility_index": tdata.get("freight_volatility_index", 0.35),
                "data_source": src_str,
                "data_source_label": src_label,
                "sources_list": src_keys,
                "live_detail": tdata,
            }

    gravar_raw(linhas)
    land_total = gravar_raw_land()
    print(f"Coletadas {land_total} linhas de malha terrestre.")
    atualizados = aplicar_no_oracle(por_porto, resumos)

    resultado_final = {
        "ingested_at": resultado["inicio"],
        "raw_total": len(linhas),
        "fontes": fontes_status,
        "ports_live": {pid: m for pid, m in atualizados.items()},
        "erros": resultado["erros"],
    }
    print(f"\n=== PORTS ATUALIZADOS COM DADO VIVO ({len(atualizados)} portos) ===")
    for pid, m in atualizados.items():
        print(f"  {pid}: score={m['congestion_score']} waiting={m['waiting_vessels']} source={m['data_source']}")
    return resultado_final


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()