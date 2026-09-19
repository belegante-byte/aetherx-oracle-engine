"""Testes da calibração observação → experiência (Fase 2 PVA)."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import duckdb  # noqa: E402

from src.engine.calibration import (  # noqa: E402
    calibrate,
    ensure_calibration_table,
    register_pair,
)


def _test_db(tmp_path):
    path = str(tmp_path / "calib_test.duckdb")
    conn = duckdb.connect(path)
    conn.execute("""
        CREATE TABLE antaq_validation (
            port_id VARCHAR, ano INTEGER, mes VARCHAR, n_atracacoes INTEGER,
            n_com_imo INTEGER, espera_atracacao_h_avg DOUBLE,
            espera_atracacao_h_med DOUBLE, espera_atracacao_h_p90 DOUBLE,
            atracado_h_avg DOUBLE, estadia_h_avg DOUBLE, gerado_em TIMESTAMP
        )
    """)
    conn.execute("""
        INSERT INTO antaq_validation VALUES
        ('BRPNG', 2025, 'jan', 200, 198, 100.0, 40.0, 300.0, 50.0, 150.0, '2026-01-01 00:00:00'),
        ('BRPNG', 2026, 'jan', 220, 218, 140.5, 42.9, 344.9, 48.1, 185.0, '2026-01-01 00:00:00'),
        ('BRRIO', 2026, 'jan', 576, 300, 30.1, 5.9, 90.8, 17.6, 40.0, '2026-01-01 00:00:00')
    """)
    ensure_calibration_table(conn)
    return conn


def test_only_queuey_port_emits_score(tmp_path):
    conn = _test_db(tmp_path)
    os.environ["DATABASE_PATH"] = str(tmp_path / "calib_test.duckdb")
    try:
        # Registra fila observada real -> BRPNG passa a ter sinal
        par = register_pair(conn, "BRPNG", 202, 33, 169, 19, source="appa")
        assert par["matched"] == 1
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
        # BRPNG com fila observada -> score emitido
        r = calibrate("BRPNG")
        assert r["congestion_score"] is not None
        assert r["historical_expected_wait_h"] > 0
        # BRRIO sem fila -> só referência, sem score (princípio de semântica)
        r2 = calibrate("BRRIO")
        assert r2["congestion_score"] is None
        assert r2["historical_expected_wait_h"] > 0
    finally:
        conn.close()


def test_confidence_cresce_com_pares(tmp_path):
    conn = _test_db(tmp_path)
    os.environ["DATABASE_PATH"] = str(tmp_path / "calib_test.duckdb")
    try:
        par = register_pair(
            conn, "BRPNG", waiting_vessels=50, ao_largo=10,
            esperados=40, atracados=15, source="appa",
        )
        assert par["matched"] == 1
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
        r = calibrate("BRPNG")
        assert r["paired_windows"] == 1
        assert r["confidence"] > 0.3  # par registered => base recency bonus
    finally:
        conn.close()