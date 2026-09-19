"""Testes da Fase 2-a: snapshot diário acumula pares de calibração BRPNG."""

import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import duckdb  # noqa: E402

import scripts.snapshot_history as sh  # noqa: E402


def _env_raw(tmp_path):
    raw = tmp_path / "raw.duckdb"
    c = duckdb.connect(str(raw))
    c.execute("""
        CREATE TABLE raw_port_lineup (
            imo VARCHAR, port_id VARCHAR, vessel_name VARCHAR, eta VARCHAR,
            status VARCHAR, cargo VARCHAR, agency VARCHAR, source VARCHAR,
            dwt DOUBLE, ingested_at TIMESTAMP
        )
    """)
    c.execute("""
        INSERT INTO raw_port_lineup VALUES
        ('1','BRPNG','NAVIO A','2026-09-20','AO_LARGO','SOJA','X','appa',80000,'2026-09-19 20:00:00'),
        ('2','BRPNG','NAVIO B','2026-09-20','ESPERADO','MILHO','Y','appa',60000,'2026-09-19 20:00:00'),
        ('3','BRPNG','NAVIO C','2026-09-19','ATRACADO','MILHO','Z','appa',60000,'2026-09-19 20:00:00')
    """)
    c.close()
    return raw


def _env_oracle(tmp_path):
    oracle = tmp_path / "oracle.duckdb"
    c = duckdb.connect(str(oracle))
    c.execute("""
        CREATE TABLE antaq_validation (
            port_id VARCHAR, ano INTEGER, mes VARCHAR, n_atracacoes INTEGER,
            n_com_imo INTEGER, espera_atracacao_h_avg DOUBLE,
            espera_atracacao_h_med DOUBLE, espera_atracacao_h_p90 DOUBLE,
            atracado_h_avg DOUBLE, estadia_h_avg DOUBLE, gerado_em TIMESTAMP
        )
    """)
    c.execute("""
        INSERT INTO antaq_validation VALUES
        ('BRPNG', 2026, 'jan', 220, 218, 140.5, 42.9, 344.9, 48.1, 185.0, '2026-01-01 00:00:00')
    """)
    c.execute("""
        CREATE TABLE port_metrics (
            port_id VARCHAR, port_name VARCHAR, country VARCHAR,
            congestion_score DOUBLE, eta_delay_days DOUBLE,
            waiting_vessels INTEGER, freight_volatility_index DOUBLE,
            estimated_daily_demurrage_usd INTEGER, data_source VARCHAR,
            updated_at TIMESTAMP
        )
    """)
    c.close()
    return oracle


def test_snapshot_register_calibration_pair(tmp_path, monkeypatch):
    raw = _env_raw(tmp_path)
    oracle = _env_oracle(tmp_path)
    monkeypatch.setenv("DATABASE_PATH", str(oracle))
    monkeypatch.setenv("RAW_DATABASE_PATH", str(raw))

    conn = duckdb.connect(str(oracle))
    sh.ensure_history_table(conn)
    n = sh.snapshot(print_fn=lambda m: None)
    # snapshot registra 0 portos (port_metrics vazia) mas deve registrar o par
    assert n >= 0

    pairs = conn.execute(
        "SELECT port_id, waiting_vessels, ao_largo, esperados, matched FROM calibration_pairs"
    ).fetchall()
    assert len(pairs) == 1
    assert pairs[0][0] == "BRPNG"
    assert pairs[0][1] == 2  # AO_LARGO + ESPERADO
    assert pairs[0][2] == 1
    assert pairs[0][3] == 1
    assert pairs[0][4] == 1

    # segunda execução no mesmo dia: idempotente (não duplica)
    sh.snapshot(print_fn=lambda m: None)
    pairs2 = conn.execute(
        "SELECT COUNT(*) FROM calibration_pairs WHERE port_id='BRPNG'"
    ).fetchone()[0]
    assert pairs2 == 1
    conn.close()


def test_register_calibration_sem_raw(tmp_path, monkeypatch):
    oracle = _env_oracle(tmp_path)
    missing = tmp_path / "nao-existe.duckdb"
    monkeypatch.setenv("DATABASE_PATH", str(oracle))
    monkeypatch.setenv("RAW_DATABASE_PATH", str(missing))

    conn = duckdb.connect(str(oracle))
    sh.snapshot(print_fn=lambda m: None)
    pairs = conn.execute("SELECT COUNT(*) FROM calibration_pairs").fetchone()[0]
    assert pairs == 0  # raw ausente -> nenhum par, sem erro
    conn.close()