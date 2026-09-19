"""Snapshot diário do oráculo para o histórico (moat temporal — alvo A).

Lê `port_metrics` do DuckDB de produção e anexa uma linha de snapshot em
`port_metrics_history` com `captured_at` UTC. NÃO é parte do startCommand:
o app continua intocado. Para ativar a periodicidade usa-se um cron/runner
externo apontando para este script (ou execução manual).

Uso:
    python scripts/snapshot_history.py          # anexa snapshot de agora
    python scripts/snapshot_history.py --test   # mostra o que faria, sem gravar
"""

import os
import sys
import argparse
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def load_env():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.getcwd(), "config", ".env"))


def db_path() -> str:
    return os.getenv("DATABASE_PATH", "data/oracle.duckdb")


def estimate_demurrage(score: float) -> int:
    from src.engine.risk_model import _estimate_demurrage
    return _estimate_demurrage(score)


def ensure_history_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS port_metrics_history (
            captured_at TIMESTAMP,
            port_id VARCHAR,
            port_name VARCHAR,
            country VARCHAR,
            congestion_score DOUBLE,
            eta_delay_days DOUBLE,
            waiting_vessels INTEGER,
            freight_volatility_index DOUBLE,
            estimated_daily_demurrage_usd INTEGER,
            data_source VARCHAR,
            as_of VARCHAR
        )
    """)


def build_rows(conn) -> list:
    rows = conn.execute("""
        SELECT port_id, port_name, country, congestion_score,
               eta_delay_days, waiting_vessels, freight_volatility_index,
               CAST(updated_at AS VARCHAR) AS as_of
        FROM port_metrics
    """).fetchall()

    captured = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    out = []
    for port_id, name, country, score, eta, waiting, vol, as_of in rows:
        demurrage = estimate_demurrage(score)
        out.append(
            (captured, port_id, name, country, score, eta, waiting, vol, demurrage,
             "static_reference_seed", as_of)
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Não grava, só mostra")
    args = parser.parse_args()

    load_env()
    import duckdb

    path = db_path()
    print(f"[SNAPSHOT] DATABASE_PATH={path}")

    if args.test:
        conn = duckdb.connect(path, read_only=True)
        rows = build_rows(conn)
        conn.close()
        for r in rows:
            print(r)
        print(f"[SNAPSHOT] --test: {len(rows)} portos (nada gravado)")
        return 0

    conn = duckdb.connect(path)
    ensure_history_table(conn)
    rows = build_rows(conn)
    conn.executemany(
        """
        INSERT INTO port_metrics_history (
            captured_at, port_id, port_name, country, congestion_score,
            eta_delay_days, waiting_vessels, freight_volatility_index,
            estimated_daily_demurrage_usd, data_source, as_of
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    n = conn.execute("SELECT COUNT(*) FROM port_metrics_history").fetchone()[0]
    conn.close()
    print(f"[SNAPSHOT] Histórico anexado: {len(rows)} portos. Total no histórico: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())