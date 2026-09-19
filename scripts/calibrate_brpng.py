"""Registra/consome pares de calibração observação→experiência (Fase 2 PVA).

BRPNG é o calibration anchor: única fonte BR que expõe fila real (ao_largo +
esperados). Cada execução anexa o par (fila observada hoje ↔ janela ANTAQ
vigente) em `calibration_pairs` e imprime o PORT STATE calibrado.

Uso:
    python scripts/calibrate_brpng.py            # registra par e mostra estado
    python scripts/calibrate_brpng.py --no-write # só mostra (dry run)

Este script é análise/calibração; NÃO altera a API nem o payload de produção.
"""

import argparse
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import duckdb
from dotenv import load_dotenv

load_dotenv("config/.env")

from src.engine.calibration import (  # noqa: E402
    calibrate,
    ensure_calibration_table,
    register_pair,
    db_path,
)


def fila_observada_bpng(inject_conn=None) -> dict | None:
    """Lê a fila real mais recente de BRPNG a partir do raw_port_lineup."""
    try:
        conn = inject_conn or duckdb.connect(
            os.getenv("RAW_DATABASE_PATH", "data/processed/aether_oracle.duckdb"),
            read_only=True,
        )
        row = conn.execute(
            """
            SELECT
              SUM(CASE WHEN status IN ('AO_LARGO','ESPERADO') THEN 1 ELSE 0 END) AS waiting,
              SUM(CASE WHEN status='AO_LARGO' THEN 1 ELSE 0 END) AS ao_largo,
              SUM(CASE WHEN status='ESPERADO' THEN 1 ELSE 0 END) AS esperados,
              SUM(CASE WHEN status='ATRACADO' THEN 1 ELSE 0 END) AS atracados
            FROM raw_port_lineup WHERE port_id='BRPNG'
            """
        ).fetchone()
        if inject_conn is None:
            conn.close()
        if row and row[0]:
            return {
                "waiting": int(row[0]), "ao_largo": int(row[1]),
                "esperados": int(row[2]), "atracados": int(row[3]),
            }
        return None
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true", help="Dry run, não grava")
    args = parser.parse_args()

    path = db_path()
    conn = duckdb.connect(path)
    try:
        ensure_calibration_table(conn)

        f = fila_observada_bpng()
        if not f:
            print("[CALIB] Nenhuma fila observada BRPNG no raw. Nada registrado.")
        else:
            par = register_pair(
                conn, "BRPNG",
                waiting_vessels=f["waiting"], ao_largo=f["ao_largo"],
                esperados=f["esperados"], atracados=f["atracados"],
                source="appa",
            )
            if par:
                print(f"[CALIB] Par BRPNG: fila={par['waiting_vessels']} "
                      f"(ao_largo={par['ao_largo']}, esperados={par['esperados']}) "
                      f"↔ ANTAQ {par['antaq_janela']}: avg={par['antaq_espera_avg_h']}h")
                if not args.no_write:
                    conn.execute(
                        """
                        INSERT INTO calibration_pairs (
                            port_id, observed_at, waiting_vessels, ao_largo,
                            esperados, atracados, source, antaq_espera_avg_h,
                            antaq_espera_med_h, antaq_espera_p90_h, antaq_janela, matched
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        list(par.values()),
                    )
                    print(f"[CALIB] par persistido ({args.no_write=})")
            else:
                print("[CALIB] Sem janela ANTAQ para BRPNG — par não formado.")

        estado = calibrate("BRPNG")
        print("\n=== PORT STATE CALIBRADO (BRPNG) ===")
        if estado:
            for k, v in estado.items():
                print(f"  {k}: {v}")
        else:
            print("  sem dados de calibração")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())