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


def _mes_ord_expr() -> str:
    """Expressão DuckDB que converte mês abreviado ('jan'..'dez') em número 1..12.

    Necessária porque a coluna `mes` da ANTAQ é VARCHAR textual; ORDER BY nela é
    léxico ('out' > 'set'), o que corromperia a escolha da janela vigente.
    """
    return """
    CASE mes
      WHEN 'jan' THEN 1 WHEN 'fev' THEN 2 WHEN 'mar' THEN 3 WHEN 'abr' THEN 4
      WHEN 'mai' THEN 5 WHEN 'jun' THEN 6 WHEN 'jul' THEN 7 WHEN 'ago' THEN 8
      WHEN 'set' THEN 9 WHEN 'out' THEN 10 WHEN 'nov' THEN 11 WHEN 'dez' THEN 12
    END
    """


def load_antaq_validation(port_id: str, years_back: int = 12) -> dict | None:
    """Recupera a validação ANTAQ (ground-truth tardio) de um porto BR.

    Retorna a agregação anual/mensal mais recente registrada pelo Espelho
    Estatístico da ANTAQ (atracação real, espera, estadia) — usada para
    comparar o sinal do oráculo com o registrado pela autoridade portuária.
    None quando a tabela ainda não existe (ex.: antes do primeiro run de
    `scripts/validate_antaq.py`) ou o porto não tem cobertura ANTAQ.
    """
    try:
        conn = _get_conn()
        tables = [r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name='antaq_validation'"
        ).fetchall()]
        if not tables:
            return None
        row = conn.execute(
            """
            SELECT ano, mes, n_atracacoes, n_com_imo,
                   espera_atracacao_h_avg, espera_atracacao_h_med,
                   espera_atracacao_h_p90, atracado_h_avg, estadia_h_avg,
                   MAX(CAST(gerado_em AS VARCHAR))
            FROM antaq_validation
            WHERE port_id = ?
            GROUP BY ano, mes, n_atracacoes, n_com_imo,
                     espera_atracacao_h_avg, espera_atracacao_h_med,
                     espera_atracacao_h_p90, atracado_h_avg, estadia_h_avg
            ORDER BY ano DESC, %s DESC
            LIMIT 1
            """
            % _mes_ord_expr(),
            [port_id],
        ).fetchone()
        if row is None:
            return None
        return {
            "source": "antaq_estatistico_aquaviario",
            "ano": row[0],
            "mes": row[1],
            "n_atracacoes": int(row[2]),
            "n_com_imo": int(row[3]),
            "espera_atracacao_h_avg": round(float(row[4]), 1) if row[4] is not None else None,
            "espera_atracacao_h_med": round(float(row[5]), 1) if row[5] is not None else None,
            "espera_atracacao_h_p90": round(float(row[6]), 1) if row[6] is not None else None,
            "atracado_h_avg": round(float(row[7]), 1) if row[7] is not None else None,
            "estadia_h_avg": round(float(row[8]), 1) if row[8] is not None else None,
            "validado_em": row[9],
        }
    except Exception:
        return None


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

    result = {
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
        "validation": load_antaq_validation(port_id),
        **extra,
    }

    # Fila real = AO_LARGO quando o detalhe vivo existe (não a soma com
    # esperados/programados, que são chegadas futuras). Se o port_metrics ainda
    # guarda um valor viciado de ingestão antiga, sobrepõe pelo dado vivo real.
    live_extra = extra.get("live")
    if live_extra and live_extra.get("ao_largo") is not None:
        result["waiting_vessels"] = live_extra["ao_largo"]

    # Estado calibrado (fila observada → experiência ANTAQ) tem precedência sobre
    # o heurístico quando existe sinal validado para o porto. Usa a conexão da
    # API (read-only) — nenhuma segunda conexão no mesmo arquivo DuckDB.
    try:
        from src.engine.calibration import calibrate as _calibrate_state
        cal = _calibrate_state(port_id, conn=conn)
        if cal and cal.get("congestion_score") is not None:
            result["congestion_score"] = cal["congestion_score"]
            result["historical_expected_wait_h"] = cal["historical_expected_wait_h"]
            result["p90_wait_h"] = cal["p90_wait_h"]
            result["eta_delay_days"] = cal["eta_delay_days"]
            result["confidence"] = cal["confidence"]
            result["paired_windows"] = cal["paired_windows"]
            result["fonte"] = cal["fonte"]
            result["semantica"] = cal["semantica"]
            # Decisão financeira ancorada nas horas reais de espera (ANTAQ),
            # não no score abstrato: US$/dia × duração esperada e pior-caso.
            result["expected_demurrage_usd"] = round(
                cal["historical_expected_wait_h"] / 24 * DEMURRAGE_BASE_USD_PER_DAY
            )
            result["p90_demurrage_usd"] = round(
                cal["p90_wait_h"] / 24 * DEMURRAGE_BASE_USD_PER_DAY
            )
    except Exception:
        pass

    return result


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