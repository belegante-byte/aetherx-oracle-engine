"""Relatório de qualidade da calibração, porto a porto (Gate 0.5, item 9).

Somente leitura (oracle + raw). Campos por porto, no contrato autorizado:
    source_history, history_last_month, live_source, last_live_observation,
    paired_windows, pair_age_distribution, confidence, p50, p90,
    calibration_status, coverage.

Estados (src/engine/pair_pipeline.classification_status):
    CALIBRATED  — ≥18 janelas matched e confiança ≥0.80
    QUALIFIED   — ≥6 matched e confiança ≥0.70
    LIMITED     — ≥1 matched, ou ≥3 pares totais
    INSUFFICIENT — caso contrário

Uso:
    .venv/bin/python scripts/calibration_report.py            # texto + JSON
    .venv/bin/python scripts/calibration_report.py --json     # só JSON
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

UNIVERSO_PORTOS = ["BRSSZ", "BRPNG", "BRRIO", "BRNIT", "BRITG"]

MES_NUM = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}


def load_env():
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.getcwd(), "config", ".env"))


def _mes_ord_expr() -> str:
    return """
    CASE mes
      WHEN 'jan' THEN 1 WHEN 'fev' THEN 2 WHEN 'mar' THEN 3 WHEN 'abr' THEN 4
      WHEN 'mai' THEN 5 WHEN 'jun' THEN 6 WHEN 'jul' THEN 7 WHEN 'ago' THEN 8
      WHEN 'set' THEN 9 WHEN 'out' THEN 10 WHEN 'nov' THEN 11 WHEN 'dez' THEN 12
    END
    """


def report_port(conn, raw, port_id: str, hoje: date) -> dict:
    from src.engine.calibration import calibrate, confidence
    from src.engine.pair_pipeline import classification_status

    r = {
        "port_id": port_id,
        "source_history": "ANTAQ (mirror HuggingFace vinicius-souza/antaq, via validate_antaq.py)",
        "history_last_month": None,
        "live_source": [],
        "last_live_observation": None,
        "paired_windows": 0,
        "matched_windows": 0,
        "pair_age_distribution": None,
        "confidence": None,
        "p50_wait_h": None,
        "p90_wait_h": None,
        "calibration_status": "INSUFFICIENT",
        "coverage": {"antaq_history": False, "live_lineup": False, "in_universe": port_id in UNIVERSO_PORTOS},
    }

    hist = conn.execute(
        """
        SELECT CAST(ano AS VARCHAR) || '-' || mes, (2026 - ano) * 12 + (1 - (%s))
        FROM antaq_validation WHERE port_id=?
        ORDER BY ano DESC, %s DESC LIMIT 1
        """
        % (_mes_ord_expr(), _mes_ord_expr()),
        [port_id],
    ).fetchone()
    if hist:
        r["history_last_month"] = hist[0]
        r["coverage"]["antaq_history"] = True

    conf = confidence(conn, port_id)
    r["confidence"] = conf["confidence"]
    r["paired_windows"] = conn.execute(
        "SELECT COUNT(*) FROM calibration_pairs WHERE port_id=?", [port_id]
    ).fetchone()[0]
    r["matched_windows"] = conf["paired_windows"]

    ages = conn.execute(
        "SELECT observed_at FROM calibration_pairs WHERE port_id=? ORDER BY observed_at",
        [port_id],
    ).fetchall()
    if ages:
        dias = [(hoje - a[0]).days for a in ages]
        r["pair_age_distribution"] = {
            "oldest_days": max(dias),
            "newest_days": min(dias),
            "mean_days": round(sum(dias) / len(dias), 1),
            "n": len(dias),
        }

    estado = calibrate(port_id, conn=conn)
    if estado:
        r["p50_wait_h"] = estado.get("historical_expected_wait_h")
        r["p90_wait_h"] = estado.get("p90_wait_h")

    if raw is not None:
        fontes = raw.execute(
            """
            SELECT source, COUNT(*), MAX(CAST(ingested_at AS VARCHAR))
            FROM raw_port_lineup WHERE port_id=? GROUP BY source ORDER BY source
            """,
            [port_id],
        ).fetchall()
        if fontes:
            r["coverage"]["live_lineup"] = True
            r["live_source"] = [
                {"source": s, "vessels": n, "ingested_at": ts} for s, n, ts in fontes
            ]
            r["last_live_observation"] = max(ts for _, _, ts in fontes)

    r["calibration_status"] = classification_status(
        r["matched_windows"], r["confidence"] or 0.0, r["paired_windows"]
    )
    return r


def build_report() -> dict:
    import duckdb

    from src.engine.calibration import db_path

    hoje = datetime.now(timezone.utc).date()
    conn = duckdb.connect(db_path(), read_only=True)
    raw_path = os.getenv("RAW_DATABASE_PATH", "data/processed/aether_oracle.duckdb")
    raw = None
    if os.path.exists(raw_path):
        raw = duckdb.connect(raw_path, read_only=True)

    port_ids = set(UNIVERSO_PORTOS)
    if raw is not None:
        port_ids |= {
            row[0]
            for row in raw.execute("SELECT DISTINCT port_id FROM raw_port_lineup").fetchall()
        }
    if conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='calibration_pairs'"
    ).fetchone()[0]:
        port_ids |= {
            row[0]
            for row in conn.execute("SELECT DISTINCT port_id FROM calibration_pairs").fetchall()
        }

    ports = [report_port(conn, raw, p, hoje) for p in sorted(port_ids)]

    fora = [p["port_id"] for p in ports if not p["coverage"]["in_universe"]]
    report = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "universe": UNIVERSO_PORTOS,
        "ports": ports,
        "coverage_notes": (
            [f"{pid}: line-up vivo mas fora do universo ANTAQ (sem mapeamento COMPLEXO_TO_PORT)" for pid in fora]
        ),
        "fornecedor_historico": {
            "mirror_stale": True,
            "nota": "mirror HF termina em 2026-01 (confirmado por --refresh em 2026-10-03); "
            "recent_antaq (>=2025-01) permanece verdadeiro para os 5 portos",
        },
    }
    if conn:
        conn.close()
    if raw:
        raw.close()
    return report


STATUS_ICON = {
    "CALIBRATED": "CALIBRATED ",
    "QUALIFIED": "QUALIFIED  ",
    "LIMITED": "LIMITED    ",
    "INSUFFICIENT": "INSUFFICIENT",
}


def check_invariants(report: dict, target_port: str = "BRPNG") -> list[str]:
    """Invariâncias do Gate 0.6 para o porto-alvo. Retorna lista de falhas;
    lista vazia = todas passam. Não altera dados."""
    failures: list[str] = []
    port = next((p for p in report["ports"] if p["port_id"] == target_port), None)
    if port is None:
        return [f"{target_port} ausente no relatório"]
    if port["matched_windows"] < 6:
        failures.append(
            f"matched={port['matched_windows']} < 6 (maturação mínima não atingida)"
        )
    if (port["confidence"] or 0.0) < 0.80:
        failures.append(
            f"confidence={port['confidence']} < 0.80 (teto v1 não sustentado)"
        )
    if port["calibration_status"] != "QUALIFIED":
        failures.append(
            f"status={port['calibration_status']} != QUALIFIED"
        )
    age = port.get("pair_age_distribution")
    if not age or age["n"] < 2:
        failures.append("menos de 2 pares — sem como verificar monotonicidade/estabilidade")
    else:
        if age["newest_days"] > 1:
            failures.append(
                f"par mais recente tem {age['newest_days']}d — ciclo diário pode ter falhado"
            )
    if not port["coverage"]["live_lineup"]:
        failures.append("sem line-up vivo na última ingestão")
    if not port["coverage"]["antaq_history"]:
        failures.append("sem janela ANTAQ (impossível parear)")
    return failures


def render_text(report: dict) -> str:
    out = []
    out.append("=" * 88)
    out.append(f"RELATÓRIO DE CALIBRAÇÃO — {report['gerado_em'][:19]}Z")
    out.append("=" * 88)
    for p in report["ports"]:
        out.append(f"\n{STATUS_ICON[p['calibration_status']]} {p['port_id']}")
        out.append(f"  source_history        : {p['source_history']}")
        out.append(f"  history_last_month    : {p['history_last_month'] or '—'}")
        live = p["live_source"] or []
        live_txt = ", ".join(f"{f['source']}({f['vessels']})" for f in live) or "—"
        out.append(f"  live_source           : {live_txt}")
        out.append(f"  last_live_observation : {p['last_live_observation'] or '—'}")
        out.append(f"  paired_windows        : {p['paired_windows']} (matched: {p['matched_windows']})")
        d = p["pair_age_distribution"]
        out.append(
            f"  pair_age_distribution : {d['n']} pares, mais antigo {d['oldest_days']}d, "
            f"mais recente {d['newest_days']}d, média {d['mean_days']}d" if d else
            "  pair_age_distribution : —"
        )
        out.append(f"  confidence            : {p['confidence']}")
        out.append(f"  p50 / p90 (h)         : {p['p50_wait_h']} / {p['p90_wait_h']}")
        out.append(f"  calibration_status    : {p['calibration_status']}")
    if report["coverage_notes"]:
        out.append("\nCOBERTURA:")
        for note in report["coverage_notes"]:
            out.append(f"  - {note}")
    out.append(f"\nHISTÓRICO: {report['fornecedor_historico']['nota']}")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Saída só em JSON")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Modo Gate 0.6: verifica invariâncias do porto-alvo; sai com código 1 se falhar.",
    )
    parser.add_argument(
        "--target-port", default="BRPNG", help="Porto-alvo do --check (default: BRPNG)."
    )
    args = parser.parse_args()

    load_env()
    report = build_report()
    if args.check:
        failures = check_invariants(report, target_port=args.target_port)
        if failures:
            print(f"[GATE-0.6] {args.target_port} NÃO PASSA ({len(failures)} falhas):")
            for f in failures:
                print(f"  - {f}")
            return 1
        port = next(p for p in report["ports"] if p["port_id"] == args.target_port)
        print(
            f"[GATE-0.6] {args.target_port} PASSA: matched={port['matched_windows']} "
            f"conf={port['confidence']} status={port['calibration_status']} "
            f"p50={port['p50_wait_h']}h p90={port['p90_wait_h']}h"
        )
        return 0
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print(render_text(report))
        print("\n(JSON completo: --json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
