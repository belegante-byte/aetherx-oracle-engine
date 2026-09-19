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

from src.ingestion.live_sources import coletar_tudo, resumo_por_porto, TO_STATUS
from src.engine.init_prod_db import PORTS


load_dotenv("config/.env")
RAW_DB = os.getenv("RAW_DATABASE_PATH", "data/processed/aether_oracle.duckdb")
ORACLE_DB = os.getenv("DATABASE_PATH", "data/oracle.duckdb")

# Quebras de congestionamento usado para derivar score a partir do line-up
# (pressão de fila = proporção de navios fora dos berços).
GRID = {
    "BRPNG": {"port_name": "Paranaguá", "country": "Brasil"},
    "BRSSZ": {"port_name": "Santos", "country": "Brasil"},
}


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
    conn.executemany(
        "INSERT INTO raw_port_lineup VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", data
    )
    total = conn.execute("SELECT COUNT(*) FROM raw_port_lineup").fetchone()[0]
    conn.close()
    return total


def _score_from_status(pid: str, resumo: dict, fonte: dict) -> dict:
    """Deriva congestion_score, waiting_vessels e eta_delay_days do line-up vivo."""
    status_keys = {k: v for k, v in resumo.items() if k.startswith("status_")}
    atracados = status_keys.get("status_ATRACADO", 0) + status_keys.get("status_EM_OPERACAO", 0)
    ao_largo = status_keys.get("status_AO_LARGO", 0)
    esperados = status_keys.get("status_ESPERADO", 0)
    programados = status_keys.get("status_PROGRAMADO", 0)

    waiting = ao_largo + esperados
    total_fora = waiting + programados
    berçado = max(atracados, 1)

    # Pressão: navios fora do berço vs. atracados. Quanto mais fila, maior.
    # Clamp entre [0.05, 0.97] para evitar extremos sintéticos.
    razao = total_fora / berçado
    score = 0.25 + 0.35 * min(razao, 2.0)
    score = max(0.05, min(0.97, score))

    # Atraso médio estimado cresce com a fila real de espera.
    if waiting == 0:
        eta_delay = 0.2
    elif waiting < 10:
        eta_delay = round(0.5 + waiting * 0.08, 2)
    elif waiting < 40:
        eta_delay = round(1.2 + waiting * 0.04, 2)
    else:
        eta_delay = round(2.4 + waiting * 0.02, 2)

    # Volatilidade de frete: derivada de mistura de cargas observada (proxy).
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
        "data_source": "live:appa+santos+lachmann",
        "data_source_label": "Live line-ups from APPA Paranaguá, Porto de Santos and Lachmann schedules.",
    }


def aplicar_no_oracle(por_porto: dict, resumos: dict) -> dict:
    from src.engine.risk_model import close_conn
    # DuckDB não permite read-only (API) e read-write (ingestão) abertos no
    # mesmo processo sobre o mesmo arquivo. Fecha a conexão da API antes.
    close_conn()
    conn = duckdb.connect(ORACLE_DB)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    atualizados = {}
    for pid, met in por_porto.items():
        meta = GRID.get(pid)
        if not meta:
            continue
        # UPSERT respeitando o CURRENT of port (se já existir, atualiza no lugar)
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
            met["waiting_vessels"], met["freight_volatility_index"], now,
            met["data_source"], met["data_source_label"],
            json.dumps({
                "ao_largo": met["ao_largo"],
                "esperados": met["esperados"],
                "atracados": met["atracados"],
                "programados": met["programados"],
            }, ensure_ascii=False),
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

    # Deriva métricas por porto com dados vivos
    por_porto = {}
    for pid in ("BRPNG", "BRSSZ"):
        resumo = resumos.get(pid)
        if not resumo or resumo.get("total", 0) == 0:
            continue
        por_porto[pid] = _score_from_status(pid, resumo, fontes_status)

    gravar_raw(linhas)
    atualizados = aplicar_no_oracle(por_porto, resumos)

    resultado_final = {
        "ingested_at": resultado["inicio"],
        "raw_total": len(linhas),
        "fontes": fontes_status,
        "ports_live": {pid: m for pid, m in atualizados.items()},
        "erros": resultado["erros"],
    }
    print("\n=== PORTS ATUALIZADOS COM DADO VIVO ===")
    for pid, m in atualizados.items():
        print(f"  {pid}: score={m['congestion_score']} waiting={m['waiting_vessels']} "
              f"(ao_largo={m['ao_largo']}, esperados={m['esperados']}, atracados={m['atracados']})")
    print(json.dumps(resultado_final, ensure_ascii=False, indent=2))
    return resultado_final


if __name__ == "__main__":
    main()