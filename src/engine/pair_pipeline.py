"""Pareamento genérico fila observada ↔ janela ANTAQ (Gate 0.5).

O writer v1 (`snapshot_history.register_calibration`) era hardcoded em BRPNG e
assumia o vocabulário de status da APPA. Os line-ups reais usam vocabulários
por fonte — medidos no raw de 2026-10-03:

    appa / portosrio_silog: AO_LARGO | ATRACADO | ESPERADO | PROGRAMADO
                            | DESPACHADO | APOIO
    santos_painel:          EM_OPERACAO          (sem categoria de fila!)
    santos:                 PROGRAMADO

Regras (nenhuma altera a fórmula de calibração v1 em engine/calibration.py):
  - categorias canônicas: waiting | berthed | scheduled; status desconhecido
    é IGNORADO (nunca contado como fila);
  - por categoria, conta apenas a fonte dominante do porto (fonte com mais
    linhas na categoria; empate resolve por nome) — evita dupla contagem de
    espelhos (appa vs appa_paranagua são os mesmos navios);
  - um par por porto/dia (idempotente por port_id + observed_at);
  - matched = waiting > 0 (semântica v1: sem fila observada, o par registra a
    observação mas não credita confiança);
  - porto sem janela ANTAQ não gera par (ex.: BRIQI/Itaqui tem line-up vivo,
    mas não está no universo de calibração).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

CANONICAL_STATUS = {
    "AO_LARGO": "waiting",
    "ATRACADO": "berthed",
    "EM_OPERACAO": "berthed",
    "ESPERADO": "scheduled",
    "PROGRAMADO": "scheduled",
}

CALIBRATED = "CALIBRATED"
QUALIFIED = "QUALIFIED"
LIMITED = "LIMITED"
INSUFFICIENT = "INSUFFICIENT"


def classification_status(matched_windows: int, confidence: float, total_pairs: int) -> str:
    """Rótulo de maturidade da calibração (relatório, não fórmula).

    Limiares contra a fórmula v1: confidence = 0.45 + min(0.35, 0.07·n) para
    janela ANTAQ recente — 0.80 só é alcançável com ≥5 pares matched, então
    CALIBRATED exige 18 para o rótulo ter substância estatística real.
    """
    if matched_windows >= 18 and confidence >= 0.80:
        return CALIBRATED
    if matched_windows >= 6 and confidence >= 0.70:
        return QUALIFIED
    if matched_windows >= 1 or total_pairs >= 3:
        return LIMITED
    return INSUFFICIENT


def summarize_lineup(raw_conn, port_id: str) -> dict | None:
    """Resume o line-up observado de um porto por categoria canônica.

    Para cada categoria, conta somente a fonte dominante (mais linhas na
    categoria; empate resolve por nome de fonte) para não somar espelhos.
    Retorna None se o porto não tem nenhuma linha.
    """
    rows = raw_conn.execute(
        """
        SELECT source, status, COUNT(*) AS n
        FROM raw_port_lineup
        WHERE port_id = ?
        GROUP BY source, status
        """,
        [port_id],
    ).fetchall()
    if not rows:
        return None

    by_category: dict[str, dict[str, int]] = {}
    for source, status, n in rows:
        cat = CANONICAL_STATUS.get(str(status).strip().upper())
        if cat is None:
            continue
        by_category.setdefault(cat, {})
        by_category[cat][source] = by_category[cat].get(source, 0) + int(n)

    counts = {"waiting": 0, "berthed": 0, "scheduled": 0}
    dominant_sources: dict[str, str] = {}
    for cat, per_source in by_category.items():
        best = sorted(per_source.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        counts[cat] = best[1]
        dominant_sources[cat] = best[0]
    return {"counts": counts, "dominant_sources": dominant_sources, "sources": sorted(
        {str(r[0]) for r in rows})}


def register_pairs(conn, raw_path: str | None = None, print_fn=print) -> list[dict]:
    """Escreve um par por porto/dia a partir do line-up raw (idempotente).

    Percorre os portos presentes no raw; para cada um com janela ANTAQ vigente
    (via register_pair v1) e sem par hoje, anexa o par em calibration_pairs.
    NÃO altera pares existentes. Retorna a lista de pares efetivamente escritos.
    """
    import duckdb

    from src.engine.calibration import ensure_calibration_table, register_pair

    raw_path = raw_path or os.getenv(
        "RAW_DATABASE_PATH", "data/processed/aether_oracle.duckdb"
    )
    ensure_calibration_table(conn)
    if not os.path.exists(raw_path):
        if print_fn:
            print_fn(f"[PAIRS] raw inexistente ({raw_path}); nenhum par.")
        return []

    today = datetime.now(timezone.utc).date()
    raw = duckdb.connect(raw_path, read_only=True)
    written: list[dict] = []
    try:
        port_ids = [
            r[0] for r in raw.execute(
                "SELECT DISTINCT port_id FROM raw_port_lineup ORDER BY port_id"
            ).fetchall()
        ]
        for port_id in port_ids:
            already = conn.execute(
                "SELECT COUNT(*) FROM calibration_pairs WHERE port_id=? AND observed_at=?",
                [port_id, today],
            ).fetchone()[0]
            if already:
                continue
            summary = summarize_lineup(raw, port_id)
            if not summary:
                continue
            counts = summary["counts"]
            par = register_pair(
                conn,
                port_id,
                waiting_vessels=int(counts["waiting"]),
                ao_largo=int(counts["waiting"]),
                esperados=int(counts["scheduled"]),
                atracados=int(counts["berthed"]),
                source=",".join(summary["sources"]),
            )
            if par is None:
                if print_fn:
                    print_fn(
                        f"[PAIRS] {port_id}: line-up vivo sem janela ANTAQ — "
                        "fora do universo de calibração (nada escrito)."
                    )
                continue
            conn.execute(
                """
                INSERT INTO calibration_pairs (
                    port_id, observed_at, waiting_vessels, ao_largo, esperados,
                    atracados, source, antaq_espera_avg_h, antaq_espera_med_h,
                    antaq_espera_p90_h, antaq_janela, matched
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    par["port_id"], par["observed_at"], par["waiting_vessels"],
                    par["ao_largo"], par["esperados"], par["atracados"],
                    par["source"], par["antaq_espera_avg_h"],
                    par["antaq_espera_med_h"], par["antaq_espera_p90_h"],
                    par["antaq_janela"], par["matched"],
                ],
            )
            written.append(par)
            if print_fn:
                print_fn(
                    f"[PAIRS] {port_id} {par['observed_at']}: "
                    f"waiting={par['waiting_vessels']} berthed={par['atracados']} "
                    f"scheduled={par['esperados']} ↔ ANTAQ {par['antaq_janela']} "
                    f"(matched={par['matched']})"
                )
    finally:
        raw.close()
    return written
