import functools
import json
import math
import os

import duckdb
from datetime import datetime, timezone
from dotenv import load_dotenv


load_dotenv("config/.env")
DB_PATH = os.getenv("DATABASE_PATH", "data/oracle.duckdb")

_CONN: "duckdb.DuckDBPyConnection | None" = None


def _get_conn() -> "duckdb.DuckDBPyConnection":
    """Conexão singleton read-only: o dataset é estático, abre 1x e reutiliza sempre."""
    global _CONN
    if _CONN is None:
        _CONN = duckdb.connect(DB_PATH, read_only=True)
    return _CONN


def close_conn():
    """Fecha a conexão singleton read-only para permitir escrita no mesmo arquivo
    (a ingestão viva grava em port_metrics; o DuckDB não permite read-only e
    read-write abertos simultaneamente no mesmo processo)."""
    global _CONN
    if _CONN is not None:
        try:
            _CONN.close()
        finally:
            _CONN = None


# NOTA DE INTEGRIDADE DE DADOS:
# Os portos brasileiros (BRSSZ/BRPNG/BRRIO/BRNIT/BRITG) são alimentados por line-ups VIVAS
# (APPA Paranaguá, Porto de Santos, Lachmann, SILOG PortosRio) via scripts/run_ingestion_live.py.
# Os demais portos usam um seed estático de referência (ver init_prod_db.py).
# Os campos `data_source` e `updated_at` tornam a proveniência explícita em toda resposta.

# Estimativa fallback baseada em estatísticas globais genéricas de congestão portuária
GLOBAL_ESTIMATE = {
    "port_name": "Unknown Port (Global Estimate)",
    "country": "Global",
    "congestion_score": 0.45,
    "eta_delay_days": 1.0,
    "waiting_vessels": 6,
    "freight_volatility_index": 0.35,
}

# Base sintética de demurrage: média ponderada da categoria de navio na fila
# (Panamax ~US$25k/dia, Capesize ~US$50k/dia). Escala com o nível de congestão.
DEMURRAGE_BASE_USD_PER_DAY = 32000.0
TREND_TAU_HOURS = 48.0
TREND_HORIZONS = (24, 48, 72)


def _estimate_demurrage(congestion_score: float) -> int:
    """Demurrage diária estimada (USD) para um navio típico esperando na fila."""
    return int(DEMURRAGE_BASE_USD_PER_DAY * (1 + 1.25 * congestion_score))


def invalidate_cache():
    """Limpa os caches LRU após uma ingestão viva para que a API sirva dados frescos."""
    calculate_port_risk.cache_clear()
    calculate_port_trend.cache_clear()


@functools.lru_cache(maxsize=1024)
def calculate_port_risk(port_id: str) -> dict:
    """
    Lê os dados reais do porto em port_metrics no DuckDB.
    Caso o porto não exista, retorna uma estimativa baseada em estatísticas globais.

    Cacheado em memória: o dataset é estático (seed roda uma única vez), então
    hits repetidos são servidos sem I/O após o primeiro acesso.
    """
    port_id = port_id.upper()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    try:
        conn = _get_conn()
        row = conn.execute("""
            SELECT port_id, port_name, country, congestion_score,
                   eta_delay_days, waiting_vessels, freight_volatility_index,
                   CAST(updated_at AS VARCHAR) AS updated_at,
                   data_source, data_source_label, live_detail
            FROM port_metrics
            WHERE port_id = ?
        """, [port_id]).fetchone()
        seed_at = conn.execute(
            "SELECT CAST(MAX(updated_at) AS VARCHAR) FROM port_metrics"
        ).fetchone()[0]
    except duckdb.Error:
        row = None
        seed_at = now

    if row is None:
        score = GLOBAL_ESTIMATE["congestion_score"]
        return {
            "port_id": port_id,
            "port_name": GLOBAL_ESTIMATE["port_name"],
            "country": GLOBAL_ESTIMATE["country"],
            "congestion_score": score,
            "eta_delay_days": GLOBAL_ESTIMATE["eta_delay_days"],
            "waiting_vessels": GLOBAL_ESTIMATE["waiting_vessels"],
            "freight_volatility_index": GLOBAL_ESTIMATE["freight_volatility_index"],
            "estimated_daily_demurrage_usd": _estimate_demurrage(score),
            "updated_at": seed_at,
            "as_of": seed_at,
            "data_source": "static_reference_seed",
            "data_source_label": "Static reference seed (not live telemetry).",
            "live_detail": None,
        }

    data_source = row[8] or "static_reference_seed"
    data_source_label = row[9] or "Static reference seed (not live telemetry)."
    live_detail = row[10]

    # Dados vivos trazem detalhe de fila real; exporta quando presente.
    extra = {}
    if data_source != "static_reference_seed" and live_detail:
        try:
            detail = json.loads(live_detail)
            extra = {
                "live": {
                    "ao_largo": detail.get("ao_largo"),
                    "esperados": detail.get("esperados"),
                    "atracados": detail.get("atracados"),
                    "programados": detail.get("programados"),
                }
            }
        except Exception:
            extra = {}

    return {
        "port_id": row[0],
        "port_name": row[1],
        "country": row[2],
        "congestion_score": row[3],
        "eta_delay_days": row[4],
        "waiting_vessels": row[5],
        "freight_volatility_index": row[6],
        "estimated_daily_demurrage_usd": _estimate_demurrage(row[3]),
        "updated_at": row[7],
        "as_of": row[7],
        "data_source": data_source,
        "data_source_label": data_source_label,
        "live_detail": live_detail,
        **extra,
    }


def _project_score(current: float, target: float, hours: float) -> float:
    """Trajetória exponencial limitada: reversão à média com constante de 48h."""
    return current + (target - current) * (1.0 - math.exp(-hours / TREND_TAU_HOURS))


def _trend_label(delta: float) -> str:
    if delta > 0.02:
        return "acelerando"
    if delta < -0.02:
        return "descongestionando"
    return "estável"


@functools.lru_cache(maxsize=1024)
def calculate_port_trend(port_id: str, horizons: tuple = TREND_HORIZONS) -> dict:
    """Projeta o congestionamento do porto para os próximos horizontes (24/48/72h).

    Modelo sintético determinístico: reversão à média com pressão do índice de
    volatilidade de frete. Retorna o rótulo de tendência (acelerando / estável /
    descongestionando) e as projeções de risco por horizonte.
    """
    base = calculate_port_risk(port_id)
    score = base["congestion_score"]
    vol = base["freight_volatility_index"]
    drift = (vol - 0.35) * 0.50 + (0.50 - score) * 0.08
    target = max(0.05, min(0.95, score + drift))

    projection = {}
    for h in horizons:
        s = round(_project_score(score, target, h), 2)
        ratio = (s / score) if score else 1.0
        projection[f"h{h}"] = {
            "congestion_score": s,
            "eta_delay_days": round(base["eta_delay_days"] * ratio, 2),
            "estimated_daily_demurrage_usd": _estimate_demurrage(s),
        }

    final = projection[f"h{horizons[-1]}"]["congestion_score"]
    return {
        "port_id": base["port_id"],
        "port_name": base["port_name"],
        "country": base["country"],
        "trend": _trend_label(final - score),
        "congestion_score": score,
        "projection": projection,
        "updated_at": base["updated_at"],
        "as_of": base["as_of"],
        "data_source": "synthetic_projection",
        "data_source_label": "Synthetic projection from static reference seed (not a live forecast).",
    }