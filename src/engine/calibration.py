"""Núcleo de calibração observação → experiência (Fase 2 do PVA).

Modelo mental (não heurística cega):

    OBSERVAÇÃO (fila ao largo / esperados, via fonte com declaração)
        ↓
    FEATURES (fila observada, estados declarados por fonte)
        ↓
    DISTRIBUIÇÃO DE ESPERA HISTÓRICA (ANTAQ, por porto/mês)
        ↓
    PORT STATE { congestion, delay, trend, confidence }

O objetivo é responder, dado o regime de fila observado hoje:

    "Quando o porto esteve nesse regime, qual distribuição de espera ocorreu?"

e não "qual número bonito cabe na escala 0-1".

Os pares (fila observada → espera no mesmo período) acumulam em
`calibration_pairs`; a confiança cresce com o número de janelas emparelhadas.
Nada aqui toca a API de produção: este módulo só GERA o estado calibrado.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import duckdb


def db_path() -> str:
    return os.getenv("DATABASE_PATH", "data/oracle.duckdb")


def _mes_ord_expr() -> str:
    """Expressão DuckDB que converte mês abreviado ('jan'..'dez') em número 1..12.

    Necessária porque a coluna `mes` da ANTAQ é VARCHAR textual; ORDER BY nela é
    léxico ('set' > 'out'), o que corromperia a escolha da janela vigente.
    """
    return """
    CASE mes
      WHEN 'jan' THEN 1 WHEN 'fev' THEN 2 WHEN 'mar' THEN 3 WHEN 'abr' THEN 4
      WHEN 'mai' THEN 5 WHEN 'jun' THEN 6 WHEN 'jul' THEN 7 WHEN 'ago' THEN 8
      WHEN 'set' THEN 9 WHEN 'out' THEN 10 WHEN 'nov' THEN 11 WHEN 'dez' THEN 12
    END
    """


def ensure_calibration_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calibration_pairs (
            port_id VARCHAR,
            observed_at DATE,
            waiting_vessels INTEGER,
            ao_largo INTEGER,
            esperados INTEGER,
            atracados INTEGER,
            source VARCHAR,
            antaq_espera_avg_h DOUBLE,
            antaq_espera_med_h DOUBLE,
            antaq_espera_p90_h DOUBLE,
            antaq_janela VARCHAR,
            matched INTEGER
        )
    """)


def register_pair(
    conn,
    port_id: str,
    waiting_vessels: int,
    ao_largo: int,
    esperados: int,
    atracados: int,
    source: str,
) -> dict | None:
    """Registra um par (fila observada hoje ↔ espera ANTAQ da janela vigente).

    Retorna o par montado (sem persistir) quando há janela ANTAQ correspondente,
    senão None. Usado pelo script de calibração e pelo snapshot diário.
    """
    row = conn.execute(
        """
        SELECT espera_atracacao_h_avg, espera_atracacao_h_med,
               espera_atracacao_h_p90, CAST(ano AS VARCHAR) || '-' || mes
        FROM antaq_validation
        WHERE port_id = ?
        ORDER BY ano DESC, %s DESC, n_atracacoes DESC
        LIMIT 1
        """
        % _mes_ord_expr(),
        [port_id],
    ).fetchone()
    if row is None:
        return None
    return {
        "port_id": port_id,
        "observed_at": datetime.now(timezone.utc).date().isoformat(),
        "waiting_vessels": waiting_vessels,
        "ao_largo": ao_largo,
        "esperados": esperados,
        "atracados": atracados,
        "source": source,
        "antaq_espera_avg_h": row[0],
        "antaq_espera_med_h": row[1],
        "antaq_espera_p90_h": row[2],
        "antaq_janela": row[3],
        "matched": 1 if waiting_vessels > 0 else 0,
    }


def antaq_distribution(conn, port_id: str) -> dict | None:
    """Distribuição mensal de espera ANTAQ do porto (toda a série)."""
    row = conn.execute(
        """
        SELECT COUNT(*),
               MIN(espera_atracacao_h_avg), ROUND(AVG(espera_atracacao_h_avg),1),
               MAX(espera_atracacao_h_avg),
               ROUND(AVG(espera_atracacao_h_med),1),
               ROUND(AVG(espera_atracacao_h_p90),1)
        FROM antaq_validation
        WHERE port_id = ?
        """,
        [port_id],
    ).fetchone()
    if row is None or row[0] == 0:
        return None
    return {
        "n_meses": row[0],
        "espera_avg_min": round(row[1], 1),
        "espera_avg_med": row[2],
        "espera_avg_max": round(row[3], 1),
        "espera_med_avg": row[4],
        "espera_p90_avg": row[5],
    }


def confidence(conn, port_id: str) -> dict:
    """Confiança do estado = f(pares emparelhados, recência da janela ANTAQ)."""
    n = conn.execute(
        "SELECT COUNT(*) FROM calibration_pairs WHERE port_id=? AND matched=1",
        [port_id],
    ).fetchone()[0]
    recente = conn.execute(
        """
        SELECT CASE WHEN MAX(ano * 100 + (%s)) >= 202501 THEN 1 ELSE 0 END
        FROM antaq_validation WHERE port_id=?
        """
        % _mes_ord_expr(),
        [port_id],
    ).fetchone()[0]
    # v1: base fixa da distribuição histórica + bônus por pares emparelhados.
    base = 0.45 if recente else 0.30
    bonus = min(0.35, n * 0.07)
    return {"confidence": round(min(0.95, base + bonus), 2), "paired_windows": n, "recent_antaq": recente}


def calibrate(port_id: str, conn=None) -> dict | None:
    """Projeta o PORT STATE calibrado para um porto, ou None sem dados.

    v1 (Fase 2, âncora BRPNG): usa a distribuição ANTAQ como experiência
    histórica e associa o regime de fila observado à mediana da espera real.
    Não faz ajuste por regressão enquanto houver <3 pares emparelhados
    (evita overfit com um único ponto).

    Aceita uma conexão injetada (ex.: read-only da API) para não abrir uma
    segunda conexão no mesmo arquivo DuckDB; senão abre a própria conexão.
    """
    own = conn is None
    if own:
        conn = duckdb.connect(db_path(), read_only=False)
    try:
        dist = antaq_distribution(conn, port_id)
        if dist is None:
            return None
        conf = confidence(conn, port_id)
        # fila mais recente (do snapshot do oráculo ou do próprio registro)
        fila = conn.execute(
            """
            SELECT waiting_vessels, ao_largo, esperados, atracados
            FROM calibration_pairs WHERE port_id=? ORDER BY observed_at DESC LIMIT 1
            """,
            [port_id],
        ).fetchone()
        n_pairs = conf["paired_windows"]

        experienced = dist["espera_avg_med"]          # mediana da média mensal histórica (h)
        p90_experienced = dist["espera_p90_avg"]       # p90 médio histórico (h)

        # Ajuste máximo conservador (sem overfit): se a fila atual é a maior já
        # vista em pares, move para a parte alta da distribuição histórica.
        if fila and fila[0]:
            if n_pairs >= 1:
                escala = min(1.15, 1.0 + 0.10 * min(1.0, fila[0] / 200.0))
            else:
                escala = 1.0
            espera_est = round(experienced * escala, 1)
            p90_est = round(p90_experienced * escala, 1)
        else:
            # Sem fila observada: NÃO emite congestion semanticamente inventado.
            # A fonte não suporta a observação → não há sinal, só referência.
            return {
                "port_id": port_id,
                "congestion_score": None,
                "historical_expected_wait_h": experienced,
                "p90_wait_h": p90_experienced,
                "eta_delay_days": None,
                "confidence": round(0.30 + 0.10 * n_pairs, 2),
                "paired_windows": n_pairs,
                "fonte": "calibracao_v1_antaq_distribuicao_somente",
                "semantica": "referencia historica (sem fila observada na fonte)",
            }

        # Score calibrado: monotônico em espera estimada, ancorado nos limites
        # observados da distribuição ANTAQ do próprio porto.
        lo, hi = dist["espera_avg_min"], dist["espera_avg_max"]
        if hi > lo:
            score = 0.05 + 0.92 * (espera_est - lo) / (hi - lo)
        else:
            score = 0.55
        score = round(max(0.05, min(0.97, score)), 3)

        # Tempo de espera esperado como produto primário (não derivado do score).
        # eta_delay em dias a partir da espera real estimada (distribuição ANTAQ).
        delay_days = round(espera_est / 24.0, 1)

        return {
            "port_id": port_id,
            "congestion_score": score,
            "historical_expected_wait_h": espera_est,
            "p90_wait_h": p90_est,
            "eta_delay_days": delay_days,
            "confidence": conf["confidence"],
            "paired_windows": n_pairs,
            "fonte": "calibracao_v1_antaq+observacao_fila",
            "semantica": "espera historica ANTAQ + fila observada",
        }
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    import json

    for pid in ("BRPNG", "BRSSZ", "BRRIO"):
        r = calibrate(pid)
        print(json.dumps(r, ensure_ascii=False, indent=2) if r else f"{pid}: sem dados")