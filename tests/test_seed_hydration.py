"""Testes da hidratação idempotente do seed (src/engine/seed_hydration.py).

Contexto: em produção `data/` é um volume persistente que sombreia o `data/` da
imagem, então o banco nasceu sem `antaq_validation` e `calibration_pairs`. Estes
testes travam as garantias: aditivo, idempotente, sem sobrescrever observação
existente, sem ressuscitar sensor morto e sem derrubar o bootstrap sem seed.
"""
import os

import duckdb
import pytest

from src.engine.seed_hydration import SEED_TABLES, hydrate_from_seed

SEED = os.path.join("seed", "oracle_seed.duckdb")
needs_seed = pytest.mark.skipif(
    not os.path.exists(SEED), reason="seed/oracle_seed.duckdb ausente (rode scripts/build_seed.py)"
)


def _mkdb(path):
    return duckdb.connect(str(path))


def _counts(conn):
    tabs = {
        r[0]
        for r in conn.execute(
            "SELECT table_name FROM duckdb_tables() WHERE database_name = current_database()"
        ).fetchall()
    }
    return {
        t: (conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] if t in tabs else None)
        for t in SEED_TABLES
    }


def _seed_counts():
    c = duckdb.connect(SEED, read_only=True)
    try:
        return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in SEED_TABLES}
    finally:
        c.close()


@needs_seed
def test_hydrates_empty_db_with_all_reference_tables(tmp_path):
    db = _mkdb(tmp_path / "oracle.duckdb")
    report = hydrate_from_seed(db)
    assert report["status"] == "ok"
    assert _counts(db) == _seed_counts()
    db.close()


@needs_seed
def test_second_run_inserts_nothing(tmp_path):
    db = _mkdb(tmp_path / "oracle.duckdb")
    hydrate_from_seed(db)
    first = _counts(db)
    report = hydrate_from_seed(db)
    assert all(v == 0 for v in report["inserted"].values()), report["inserted"]
    assert _counts(db) == first
    db.close()


@needs_seed
def test_never_overwrites_existing_observation(tmp_path):
    """Linha existente (mesmo que seja mais velha) NÃO é sobrescrita nem duplicada."""
    db = _mkdb(tmp_path / "oracle.duckdb")
    hydrate_from_seed(db)
    pid = db.execute("SELECT port_id FROM port_metrics ORDER BY port_id LIMIT 1").fetchone()[0]
    db.execute(
        "UPDATE port_metrics SET congestion_score=0.99, data_source='static_reference_seed' "
        "WHERE port_id=?",
        [pid],
    )
    hydrate_from_seed(db)
    rows = db.execute(
        "SELECT COUNT(*), MAX(congestion_score) FROM port_metrics WHERE port_id=?", [pid]
    ).fetchone()
    assert rows == (1, 0.99)
    db.close()


@needs_seed
def test_never_resurrects_dead_sensor_rows(tmp_path):
    """Mesmo que o seed traga live:*, a hidratação não pode inserir leitura velha."""
    conn = _mkdb(tmp_path / "oracle.duckdb")
    seed_path = str(tmp_path / "seed.duckdb")
    seed = _mkdb(seed_path)
    seed.execute(
        "CREATE TABLE port_metrics(port_id VARCHAR, port_name VARCHAR, data_source VARCHAR, updated_at TIMESTAMP)"
    )
    seed.execute(
        "INSERT INTO port_metrics VALUES ('ZZZZZ','Porto Morto','live:santospainel','2026-09-20 10:00:00')"
    )
    seed.close()
    report = hydrate_from_seed(conn, seed_path)
    n = conn.execute("SELECT COUNT(*) FROM port_metrics").fetchone()[0]
    assert n == 0
    assert report["live_rows_blocked"].get("port_metrics") == 1
    conn.close()


@needs_seed
def test_missing_seed_is_noop_and_logged(tmp_path):
    db = _mkdb(tmp_path / "oracle.duckdb")
    db.execute("CREATE TABLE port_metrics(port_id VARCHAR)")
    db.execute("INSERT INTO port_metrics VALUES ('BRSSZ')")
    report = hydrate_from_seed(db, str(tmp_path / "nao_existe.duckdb"))
    assert report["status"] == "skipped_no_seed"
    assert _counts(db)["port_metrics"] == 1
    logs = db.execute("SELECT status FROM seed_hydration_log").fetchall()
    assert ("skipped_no_seed",) in logs
    db.close()


@needs_seed
def test_adds_missing_column_without_dropping_table(tmp_path):
    """Migração aditiva: coluna que falta é criada, dados existentes ficam."""
    db = _mkdb(tmp_path / "oracle.duckdb")
    hydrate_from_seed(db)
    cols = {
        r[0]
        for r in db.execute(
            "SELECT column_name FROM duckdb_columns() WHERE table_name='calibration_pairs'"
        ).fetchall()
    }
    victim = sorted(cols)[0]
    db.execute(f"ALTER TABLE calibration_pairs DROP COLUMN {victim}")
    db.execute("INSERT INTO calibration_pairs (port_id) VALUES ('BRSSZ')")
    report = hydrate_from_seed(db)
    assert victim in report["added_columns"].get("calibration_pairs", [])
    n = db.execute(
        "SELECT COUNT(*) FROM calibration_pairs WHERE port_id='BRSSZ'"
    ).fetchone()[0]
    assert n == 1
    assert _counts(db)["calibration_pairs"] >= _seed_counts()["calibration_pairs"]
    db.close()


@needs_seed
def test_log_records_seed_provenance(tmp_path):
    db = _mkdb(tmp_path / "oracle.duckdb")
    hydrate_from_seed(db)
    row = db.execute(
        "SELECT status, seed_sha256, seed_built_at FROM seed_hydration_log"
    ).fetchone()
    assert row[0] == "ok"
    assert len(row[1]) == 64
    assert row[2]
    db.close()
