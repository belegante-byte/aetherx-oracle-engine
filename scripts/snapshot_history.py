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
               CAST(updated_at AS VARCHAR) AS as_of,
               COALESCE(data_source, 'static_reference_seed') AS data_source
        FROM port_metrics
    """).fetchall()

    captured = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    out = []
    for port_id, name, country, score, eta, waiting, vol, as_of, ds in rows:
        demurrage = estimate_demurrage(score)
        out.append(
            (captured, port_id, name, country, score, eta, waiting, vol, demurrage,
             ds, as_of)
        )
    return out


def snapshot(print_fn=print, per_port_latest_day: bool = True) -> int:
    """Anexa um snapshot de agora ao histórico e retorna o total de linhas.

    Se per_port_latest_day=True (padrão), mantém apenas a última captura por
    porto/dia, evitando poluir o histórico quando rodado várias vezes no dia.
    """
    import duckdb

    path = db_path()
    conn = duckdb.connect(path)
    try:
        ensure_history_table(conn)
        rows = build_rows(conn)
        if per_port_latest_day:
            # Uma linha por porto/dia: remove as capturas do dia corrente antes
            # de inserir as novas (evita duplicatas quando roda várias vezes).
            conn.execute("""
                DELETE FROM port_metrics_history
                WHERE CAST(captured_at AS DATE) = (SELECT MAX(CAST(captured_at AS DATE)) FROM port_metrics_history)
            """)
        conn.executemany(
            """
            INSERT INTO port_metrics_history (
                captured_at, port_id, port_name, country, congestion_score,
                eta_delay_days, waiting_vessels, freight_volatility_index,
                estimated_daily_demurrage_usd, data_source, as_of
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        ) if rows else None
        n = conn.execute("SELECT COUNT(*) FROM port_metrics_history").fetchone()[0]
        # Calibração BRPNG (anchor): acumula pares (fila observada hoje ↔ janela
        # ANTAQ vigente). Nunca pode quebrar o snapshot.
        try:
            register_calibration(conn, print_fn=print_fn)
        except Exception as e:
            if print_fn:
                print_fn(f"[SNAPSHOT] calibração ignorada: {type(e).__name__}: {e}")
    finally:
        conn.close()
    if print_fn:
        print_fn(f"[SNAPSHOT] Histórico anexado: {len(rows)} portos. Total: {n}")
    return n


def register_calibration(conn, print_fn=print) -> None:
    """Acumula pares de calibração BRPNG (Fase 2 — anchor).

    Lê a fila real observada (ao_largo + esperados) do raw DB e emparelha com a
    janela ANTAQ vigente. Um par por porto/dia (idempotente por data).
    """
    from src.engine.calibration import ensure_calibration_table, register_pair

    ensure_calibration_table(conn)
    hoje = datetime.now(timezone.utc).date()
    ja_registrado = conn.execute(
        "SELECT COUNT(*) FROM calibration_pairs WHERE port_id='BRPNG' AND observed_at=?",
        [hoje],
    ).fetchone()[0]
    if ja_registrado:
        return

    raw_path = os.getenv("RAW_DATABASE_PATH", "data/processed/aether_oracle.duckdb")
    if not os.path.exists(raw_path):
        return
    import duckdb

    raw = duckdb.connect(raw_path, read_only=True)
    try:
        r = raw.execute(
            """
            SELECT
              SUM(CASE WHEN status IN ('AO_LARGO','ESPERADO') THEN 1 ELSE 0 END),
              SUM(CASE WHEN status='AO_LARGO' THEN 1 ELSE 0 END),
              SUM(CASE WHEN status='ESPERADO' THEN 1 ELSE 0 END),
              SUM(CASE WHEN status='ATRACADO' THEN 1 ELSE 0 END)
            FROM raw_port_lineup WHERE port_id='BRPNG'
            """
        ).fetchone()
    finally:
        raw.close()
    if not r or not r[0]:
        return

    par = register_pair(
        conn, "BRPNG",
        waiting_vessels=int(r[0]), ao_largo=int(r[1]),
        esperados=int(r[2]), atracados=int(r[3] or 0),
        source="appa",
    )
    if par:
        conn.execute(
            """
            INSERT INTO calibration_pairs (
                port_id, observed_at, waiting_vessels, ao_largo, esperados,
                atracados, source, antaq_espera_avg_h, antaq_espera_med_h,
                antaq_espera_p90_h, antaq_janela, matched
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            list(par.values()),
        )
        if print_fn:
            print_fn(
                f"[CALIB] par BRPNG {par['observed_at']}: fila={par['waiting_vessels']} "
                f"↔ ANTAQ {par['antaq_janela']} avg={round(par['antaq_espera_avg_h'],1)}h"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Não grava, só mostra")
    args = parser.parse_args()

    load_env()

    path = db_path()
    print(f"[SNAPSHOT] DATABASE_PATH={path}")

    if args.test:
        import duckdb

        conn = duckdb.connect(path, read_only=True)
        rows = build_rows(conn)
        conn.close()
        for r in rows:
            print(r)
        print(f"[SNAPSHOT] --test: {len(rows)} portos (nada gravado)")
        return 0

    snapshot()
    return 0


if __name__ == "__main__":
    sys.exit(main())