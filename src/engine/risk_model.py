import functools
import json
import math
import os

import duckdb
from datetime import datetime, timezone
from dotenv import load_dotenv


load_dotenv("config/.env")
_raw_db_path = os.getenv("DATABASE_PATH", "data/oracle.duckdb")
DB_PATH = _raw_db_path if os.path.exists(_raw_db_path) else "data/oracle.duckdb"

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
    try:
        from src.products.gp5.fiscal import evaluate_fiscal_routing
        evaluate_fiscal_routing.cache_clear()
    except ImportError:
        pass
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

    conn = None
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

    # Enriquecimento com telemetria de referência (Estreitos, Ásia, Europa, África).
    # INTEGRIDADE: os dicionários em live_sources.py são REFERÊNCIA CALIBRADA
    # (sources=["static_reference_seed"]), NÃO telemetria viva. Só emitimos
    # rótulos live:* quando a fonte declara observação real.
    try:
        from src.ingestion.live_sources import (
            fetch_asian_port_congestion,
            fetch_european_port_congestion,
            fetch_chokepoint_and_african_telemetry
        )
        live_global = {
            **fetch_asian_port_congestion(),
            **fetch_european_port_congestion(),
            **fetch_chokepoint_and_african_telemetry()
        }
        # Precedência de dados reais: se o port_metrics carrega uma observação
        # viva (live:*) no DuckDB, serve ELA — o dicionário estático de
        # referência NUNCA pode encobrir telemetria real do sensor.
        _db_is_live = bool(row and (row[8] or "").startswith("live:"))
        if port_id in live_global and not _db_is_live:
            pinfo = live_global[port_id]
            score = pinfo["congestion_score"]
            wait_hours = pinfo.get("median_wait_hours")
            wait_text = f"Median wait {wait_hours}h" if wait_hours is not None else f"Transits {pinfo.get('daily_transits', 'n/a')}/day ({pinfo.get('pct_of_normal_baseline', '100')}% baseline)"
            yard_text = f", Yard Utilization {pinfo['yard_utilization_pct']}%" if "yard_utilization_pct" in pinfo else ""
            rail_text = f", Intermodal Rail: {pinfo['intermodal_rail_status']}" if "intermodal_rail_status" in pinfo else ""
            live_sources = [
                s for s in (pinfo.get("sources") or [])
                if s and s != "static_reference_seed"
            ]
            if live_sources:
                return {
                    "port_id": port_id,
                    "port_name": pinfo["port_name"],
                    "country": pinfo["country"],
                    "congestion_score": score,
                    "eta_delay_days": pinfo["eta_delay_days"],
                    "waiting_vessels": pinfo["waiting_vessels"],
                    "freight_volatility_index": 0.40,
                    "estimated_daily_demurrage_usd": _estimate_demurrage(score),
                    "updated_at": pinfo["as_of"],
                    "as_of": pinfo["as_of"],
                    "data_source": f"live:{'+'.join(live_sources)}",
                    "data_source_label": (
                        f"Live AIS & Traffic intelligence via {', '.join(live_sources)} "
                        f"({wait_text}{yard_text}{rail_text})."
                    ),
                    "live_detail": json.dumps(pinfo),
                    "decision_grade": "conditional",
                    "signal": {
                        "level": "ELEVATED OPERATIONAL PRESSURE" if score >= 0.45 else "MODERATE / LOW PRESSURE",
                        "live_observation": True,
                        "queue_vessels": pinfo["waiting_vessels"],
                        "expected_delay_days": pinfo["eta_delay_days"],
                        "demurrage_expected_usd": int(pinfo["eta_delay_days"] * DEMURRAGE_BASE_USD_PER_DAY),
                        "confidence": 0.94,
                        "provenance": f"live:{'+'.join(live_sources)}",
                        "decision_implication": f"Live stream indicates {pinfo.get('status', 'operational').lower()} conditions at {pinfo['port_name']} ({pinfo['country']}).",
                        "as_of": pinfo["as_of"],
                    }
                }
            # Referência calibrada/estática: rótulo honesto, sem fingir telemetria viva.
            return {
                "port_id": port_id,
                "port_name": pinfo["port_name"],
                "country": pinfo["country"],
                "congestion_score": score,
                "eta_delay_days": pinfo["eta_delay_days"],
                "waiting_vessels": pinfo["waiting_vessels"],
                "freight_volatility_index": pinfo.get("freight_volatility_index", 0.40),
                "estimated_daily_demurrage_usd": _estimate_demurrage(score),
                "updated_at": pinfo["as_of"],
                "as_of": pinfo["as_of"],
                "data_source": "calibrated_reference_seed",
                "data_source_label": (
                    "Calibrated reference seed (static model baseline, NOT live telemetry). "
                    f"Reference conditions: {wait_text}{yard_text}{rail_text}."
                ),
                "live_detail": json.dumps({**pinfo, "source": "calibrated_reference_seed", "sources": ["calibrated_reference_seed"]}),
                "decision_grade": "reference",
                "signal": {
                    "level": "ELEVATED OPERATIONAL PRESSURE" if score >= 0.45 else "MODERATE / LOW PRESSURE",
                    "live_observation": False,
                    "queue_vessels": pinfo["waiting_vessels"],
                    "expected_delay_days": pinfo["eta_delay_days"],
                    "demurrage_expected_usd": int(pinfo["eta_delay_days"] * DEMURRAGE_BASE_USD_PER_DAY),
                    "confidence": None,
                    "provenance": "calibrated_reference_seed",
                    "decision_implication": (
                        f"Reference baseline only — NOT a live observation. "
                        f"Indicates modeled reference conditions at {pinfo['port_name']} ({pinfo['country']}); "
                        "do not use as real-time field data."
                    ),
                    "as_of": pinfo["as_of"],
                }
            }
    except Exception:
        pass

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


    # Enriquecimento padrao (signal e decision_grade)
    is_live = result.get("data_source", "").startswith("live:")
    score = result.get("congestion_score", 0.5)
    result["decision_grade"] = "decision" if is_live else "reference"
    
    if result.get("signal") is None:
        result["signal"] = {
            "level": "ELEVATED OPERATIONAL PRESSURE" if score >= 0.45 else "MODERATE / LOW PRESSURE",
            "live_observation": is_live,
            "queue_vessels": result.get("waiting_vessels", 0),
            "expected_delay_days": result.get("eta_delay_days", 0),
            "demurrage_expected_usd": int(result.get("eta_delay_days", 0) * DEMURRAGE_BASE_USD_PER_DAY),
            "confidence": 0.94 if is_live else None,
            "provenance": result.get("data_source"),
            "decision_implication": f"{'Live stream' if is_live else 'Reference seed'} indicates operational pressure at {result['port_name']}.",
            "as_of": result.get("as_of")
        }

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
    """Projeta o congestionamento do porto para os próximos horizontes (24/48/72h)
    usando regressão linear local (Numpy) sobre o histórico real (DuckDB).
    """
    import numpy as np
    
    base = calculate_port_risk(port_id)
    score = base["congestion_score"]
    
    # Busca histórico das últimas 168 horas (7 dias)
    conn = _get_conn()
    history = conn.execute(
        """
        SELECT captured_at, congestion_score
        FROM port_metrics_history
        WHERE port_id = ?
          AND captured_at >= current_timestamp - interval '7 days'
        ORDER BY captured_at ASC
        """,
        [port_id]
    ).fetchall()
    
    projection = {}
    
    if len(history) < 3:
        # Fallback se não houver histórico suficiente (ex: seed recente)
        target = score
        for h in horizons:
            projection[f"h{h}"] = {
                "congestion_score": score,
                "eta_delay_days": base["eta_delay_days"],
                "estimated_daily_demurrage_usd": _estimate_demurrage(score),
            }
        trend_label = "estável"
        final_score = score
    else:
        # Converte para horas relativas (0 = mais antigo do período)
        import datetime
        times = [r[0] for r in history]
        scores = [r[1] for r in history]
        
        t0 = times[-1] # current time
        x = np.array([(t - t0).total_seconds() / 3600.0 for t in times])
        y = np.array(scores)
        
        # Regressão linear simples: y = mx + c
        m, c = np.polyfit(x, y, 1)
        
        # Previsão
        for h in horizons:
            pred_score = m * h + c
            # Limita entre 0.05 e 0.95
            s = round(max(0.05, min(0.95, float(pred_score))), 2)
            ratio = (s / score) if score else 1.0
            projection[f"h{h}"] = {
                "congestion_score": s,
                "eta_delay_days": round(base["eta_delay_days"] * ratio, 2),
                "estimated_daily_demurrage_usd": _estimate_demurrage(s),
            }
        
        final_score = projection[f"h{horizons[-1]}"]["congestion_score"]
        delta = final_score - score
        trend_label = _trend_label(delta)

    return {
        "port_id": base["port_id"],
        "port_name": base["port_name"],
        "country": base["country"],
        "trend": trend_label,
        "congestion_score": score,
        "projection": projection,
        "updated_at": base["updated_at"],
        "as_of": base["as_of"],
        "data_source": "predictive_ml_regression",
        "data_source_label": "Local ML Regression (Numpy) trained on historical telemetry.",
    }

HISTORY_MAX_DAYS = 90  # contrato Pro: séries históricas de até 90 dias


def get_port_history(port_id: str, days: int = HISTORY_MAX_DAYS) -> dict:
    """Série histórica observada de um porto (contrato Pro: até 90 dias).

    Integraidade (sem over-promise): devolve SOMENTE observações realmente
    persistidas em `port_metrics_history` e declara a cobertura real
    (`observations`, `first_seen`, `last_seen`, `span_days`, `days_requested`).
    Um porto com histórico curto não é preenchido com dado sintético — o
    cliente vê a lacuna.
    """
    days = max(1, min(int(days), HISTORY_MAX_DAYS))
    upper = (port_id or "").strip().upper()
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT captured_at, congestion_score, eta_delay_days, waiting_vessels,
               freight_volatility_index, data_source
        FROM port_metrics_history
        WHERE port_id = ?
          AND captured_at >= current_timestamp - (? * interval '1 day')
        ORDER BY captured_at ASC
        """,
        [upper, days],
    ).fetchall()
    series = [
        {
            "captured_at": r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0]),
            "congestion_score": r[1],
            "eta_delay_days": r[2],
            "waiting_vessels": r[3],
            "freight_volatility_index": r[4],
            "data_source": r[5],
        }
        for r in rows
    ]
    first_seen = series[0]["captured_at"] if series else None
    last_seen = series[-1]["captured_at"] if series else None
    span_days = 0.0
    if series:
        try:
            span_days = round(
                (datetime.fromisoformat(last_seen) - datetime.fromisoformat(first_seen)).total_seconds()
                / 86400.0,
                2,
            )
        except Exception:
            span_days = 0.0
    return {
        "port_id": upper,
        "series": series,
        "observations": len(series),
        "days_requested": days,
        "days_max": HISTORY_MAX_DAYS,
        "span_days": span_days,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "data_source": "observed_history" if series else "no_history_observations",
        "data_source_label": (
            "Série de observações persistidas (snapshot history). Não é previsão."
            if series
            else "Sem observações históricas persistidas para a janela solicitada."
        ),
        "coverage_note": (
            f"Série observada: {len(series)} ponto(s) em {span_days}d de uma janela "
            f"contratada de até {days}d (máx {HISTORY_MAX_DAYS}d). Onde faltam "
            "observações, não há interpolação — a lacuna é explícita."
        ),
    }
