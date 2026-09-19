"""Ciclo diário local de acúmulo BRPNG (Fase 2-b).

Roda a ingestão viva (line-up real APPA -> raw DB + port_metrics) e em seguida o
snapshot (port_metrics_history + par de calibração fila↔ANTAQ). Idempotente por
data: reexecutar no mesmo dia não duplica o par (register_calibration ignora se
o observed_at já existe; snapshot sobrescreve a captura do dia corrente).

Uso:
    python scripts/acumular_brpng_diario.py          # ciclo completo
    python scripts/acumular_brpng_diario.py --only-snapshot  # só o par/histórico
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def load_env():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.getcwd(), "config", ".env"))


def main() -> int:
    import argparse
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only-snapshot", action="store_true",
        help="Pula a ingestão viva; só registra snapshot e par do dia.",
    )
    args = parser.parse_args()

    load_env()
    print(f"[ACUMULA] {datetime.now(timezone.utc).isoformat()} faz="
          f"{datetime.now(timezone.utc).date()}")

    if not args.only_snapshot:
        from scripts.run_ingestion_live import main as ingressao
        try:
            ingressao()
        except Exception as e:
            print(f"[ACUMULA] ingestão falhou: {type(e).__name__}: {e}")

    from scripts.snapshot_history import snapshot
    n = snapshot(print_fn=lambda m: print(m))
    print(f"[ACUMULA] histórico total: {n} linhas")

    import duckdb
    from src.engine.risk_model import DB_PATH as oracle_db_path
    conn = duckdb.connect(oracle_db_path, read_only=True)
    pares = conn.execute(
        "SELECT observed_at, waiting_vessels, antaq_janela, matched "
        "FROM calibration_pairs WHERE port_id='BRPNG' ORDER BY observed_at"
    ).fetchall()
    conn.close()
    print(f"[ACUMULA] pares BRPNG: {len(pares)}")
    for p in pares:
        print(f"  {p[0]} fila={p[1]} ↔ ANTAQ {p[2]} matched={p[3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())