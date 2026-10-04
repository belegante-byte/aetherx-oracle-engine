"""Gate 0.5 — pipeline de pareamento observação live ↔ ANTAQ (multi-porto).

Contrato autorizado (nenhum item toca a fórmula de calibração v1):
  1. Vocabulário de status por fonte (Santos não tem AO_LARGO).
  2. Idempotência: a mesma observação/dia não cria pares duplicados.
  3. Dedup de espelho: appa e appa_paranagua são os mesmos navios — só a fonte
     dominante por categoria conta (bug de dupla contagem do writer v1).
  4. BRPNG mantém a semântica v1 (fila = AO_LARGO; ESPERADO não soma).
  5. Porto com line-up vivo mas sem janela ANTAQ (ex.: BRIQI) não gera par.
  6. Uma observação live nova alimenta calibrate() sem seed manual.
  7. matched=0 (sem fila observada) registra o par mas NÃO credita confiança.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import duckdb  # noqa: E402

from src.engine import pair_pipeline as pp  # noqa: E402
from src.engine.calibration import calibrate, confidence  # noqa: E402

RAW_DDL = """
    CREATE TABLE raw_port_lineup (
        imo VARCHAR, port_id VARCHAR, vessel_name VARCHAR, eta VARCHAR,
        status VARCHAR, cargo VARCHAR, agency VARCHAR, source VARCHAR,
        dwt DOUBLE, ingested_at TIMESTAMP
    )
"""

ANTAQ_DDL = """
    CREATE TABLE antaq_validation (
        port_id VARCHAR, ano INTEGER, mes VARCHAR, n_atracacoes INTEGER,
        n_com_imo INTEGER, espera_atracacao_h_avg DOUBLE,
        espera_atracacao_h_med DOUBLE, espera_atracacao_h_p90 DOUBLE,
        atracado_h_avg DOUBLE, estadia_h_avg DOUBLE, gerado_em TIMESTAMP
    )
"""


def _oracle(tmp_path, janelas: dict):
    oracle = tmp_path / "oracle.duckdb"
    c = duckdb.connect(str(oracle))
    c.execute(ANTAQ_DDL)
    for port_id, (avg, med, p90) in janelas.items():
        c.execute(
            "INSERT INTO antaq_validation VALUES (?, 2026, 'jan', 200, 195, ?, ?, ?, 40.0, 180.0, '2026-01-01')",
            [port_id, avg, med, p90],
        )
    c.close()
    return oracle


def _raw(tmp_path, linhas, idade_h: float = 1.0):
    """Grava line-up com observação com `idade_h` horas (default: fresca)."""
    from datetime import datetime, timedelta, timezone

    raw = tmp_path / "raw.duckdb"
    ing = (datetime.now(timezone.utc) - timedelta(hours=idade_h)).strftime("%Y-%m-%d %H:%M:%S")
    c = duckdb.connect(str(raw))
    c.execute(RAW_DDL)
    for i, (port_id, status, source) in enumerate(linhas):
        c.execute(
            "INSERT INTO raw_port_lineup VALUES (?, ?, 'NAVIO', '2026-10-03', ?, 'GRANEL', 'AG', ?, 50000.0, ?)",
            [str(i), port_id, status, source, ing],
        )
    c.close()
    return raw


def _pairs(conn, port_id=None):
    q = "SELECT * FROM calibration_pairs"
    args = []
    if port_id:
        q += " WHERE port_id=?"
        args.append(port_id)
    return conn.execute(q, args).fetchall()


def test_vocabulary_santos_has_no_waiting(tmp_path):
    """Santos emite EM_OPERACAO/PROGRAMADO — fila observada é 0, honestamente."""
    oracle = _oracle(tmp_path, {"BRSSZ": (120.0, 60.0, 300.0)})
    raw = _raw(
        tmp_path,
        [("BRSSZ", "EM_OPERACAO", "santos_painel")] * 5
        + [("BRSSZ", "PROGRAMADO", "santos")] * 7,
    )
    conn = duckdb.connect(str(oracle))
    written = pp.register_pairs(conn, raw_path=str(raw), print_fn=None)
    conn.close()

    assert len(written) == 1
    par = written[0]
    assert par["port_id"] == "BRSSZ"
    assert par["waiting_vessels"] == 0  # sem AO_LARGO no vocabulário da fonte
    assert par["matched"] == 0
    # Mas a observação fica registrada como metadado (berthed/scheduled).
    conn = duckdb.connect(str(oracle), read_only=True)
    row = conn.execute(
        "SELECT esperados, atracados FROM calibration_pairs WHERE port_id='BRSSZ'"
    ).fetchone()
    conn.close()
    assert row == (7, 5)


def test_unknown_status_is_ignored_not_counted(tmp_path):
    oracle = _oracle(tmp_path, {"BRPNG": (100.0, 50.0, 200.0)})
    raw = _raw(
        tmp_path,
        [("BRPNG", "DESPACHADO", "appa"), ("BRPNG", "APOIO", "appa"),
         ("BRPNG", "STATUS_ESTRANHO", "fonte_nova"), ("BRPNG", "AO_LARGO", "appa")],
    )
    conn = duckdb.connect(str(oracle))
    written = pp.register_pairs(conn, raw_path=str(raw), print_fn=None)
    conn.close()
    assert len(written) == 1
    assert written[0]["waiting_vessels"] == 1  # só o AO_LARGO


def test_mirror_sources_are_not_double_counted(tmp_path):
    """appa e appa_paranagua espelham os mesmos navios: conta só a dominante."""
    oracle = _oracle(tmp_path, {"BRPNG": (100.0, 50.0, 200.0)})
    raw = _raw(
        tmp_path,
        [("BRPNG", "AO_LARGO", "appa")] * 3
        + [("BRPNG", "AO_LARGO", "appa_paranagua")] * 3
        + [("BRPNG", "ESPERADO", "appa")] * 2
        + [("BRPNG", "ESPERADO", "appa_paranagua")] * 2
        + [("BRPNG", "ESPERADO", "lachmann")] * 6,
    )
    conn = duckdb.connect(str(oracle))
    written = pp.register_pairs(conn, raw_path=str(raw), print_fn=None)
    conn.close()
    assert len(written) == 1
    assert written[0]["waiting_vessels"] == 3   # NÃO 6 (bug v1 somava os espelhos)
    assert written[0]["esperados"] == 6         # lachmann é a fonte dominante de ESPERADO
    assert written[0]["source"] == "appa,appa_paranagua,lachmann"


def test_idempotency_same_day_no_duplicates(tmp_path):
    oracle = _oracle(tmp_path, {"BRPNG": (100.0, 50.0, 200.0), "BRRIO": (90.0, 45.0, 180.0)})
    raw = _raw(
        tmp_path,
        [("BRPNG", "AO_LARGO", "appa")] * 4
        + [("BRRIO", "AO_LARGO", "portosrio_silog")] * 2,
    )
    conn = duckdb.connect(str(oracle))
    first = pp.register_pairs(conn, raw_path=str(raw), print_fn=None)
    second = pp.register_pairs(conn, raw_path=str(raw), print_fn=None)
    third = pp.register_pairs(conn, raw_path=str(raw), print_fn=None)
    conn.close()
    assert len(first) == 2
    assert second == [] and third == []
    conn = duckdb.connect(str(oracle), read_only=True)
    assert len(_pairs(conn)) == 2
    conn.close()


def test_brpng_semantics_unchanged(tmp_path):
    """Fila real = AO_LARGO; ESPERADO é programação futura (semântica v1)."""
    oracle = _oracle(tmp_path, {"BRPNG": (140.5, 42.9, 344.9)})
    raw = _raw(
        tmp_path,
        [("BRPNG", "AO_LARGO", "appa")] * 2
        + [("BRPNG", "ESPERADO", "appa")] * 10
        + [("BRPNG", "ATRACADO", "appa")] * 3,
    )
    conn = duckdb.connect(str(oracle))
    written = pp.register_pairs(conn, raw_path=str(raw), print_fn=None)
    conn.close()
    assert written[0]["waiting_vessels"] == 2
    assert written[0]["ao_largo"] == 2
    assert written[0]["esperados"] == 10
    assert written[0]["atracados"] == 3
    assert written[0]["matched"] == 1
    assert written[0]["antaq_janela"] == "2026-jan"


def test_port_without_antaq_window_gets_no_pair(tmp_path):
    """BRIQI tem line-up vivo mas não está no universo ANTAQ: nada é escrito."""
    oracle = _oracle(tmp_path, {"BRPNG": (100.0, 50.0, 200.0)})
    raw = _raw(
        tmp_path,
        [("BRIQI", "AO_LARGO", "emar_itaqui")] * 8
        + [("BRPNG", "AO_LARGO", "appa")],
    )
    conn = duckdb.connect(str(oracle))
    written = pp.register_pairs(conn, raw_path=str(raw), print_fn=None)
    conn.close()
    assert [w["port_id"] for w in written] == ["BRPNG"]
    conn = duckdb.connect(str(oracle), read_only=True)
    assert conn.execute("SELECT COUNT(*) FROM calibration_pairs WHERE port_id='BRIQI'").fetchone()[0] == 0
    conn.close()


def test_live_observation_feeds_calibration_without_seed(tmp_path):
    """Condição de fechamento do Gate 0.5: observação live → par → calibrate()."""
    oracle = _oracle(tmp_path, {"BRSSZ": (120.0, 60.0, 300.0)})
    raw = _raw(tmp_path, [("BRSSZ", "AO_LARGO", "fonte_teste")] * 5)
    conn = duckdb.connect(str(oracle))
    pp.register_pairs(conn, raw_path=str(raw), print_fn=None)
    estado = calibrate("BRSSZ", conn=conn)
    conn.close()
    # Sem seed, sem hydration: só o raw de hoje + a série ANTAQ do oráculo.
    assert estado is not None
    assert estado["congestion_score"] is not None  # há fila observada → score emite
    assert estado["paired_windows"] == 1
    assert estado["semantica"] == "espera historica ANTAQ + fila observada"


def test_matched_zero_does_not_credit_confidence(tmp_path):
    """Par matched=0 registra observação mas a confiança v1 não cresce com ele."""
    oracle = _oracle(tmp_path, {"BRSSZ": (120.0, 60.0, 300.0)})
    raw = _raw(tmp_path, [("BRSSZ", "EM_OPERACAO", "santos_painel")])
    conn = duckdb.connect(str(oracle))
    pp.register_pairs(conn, raw_path=str(raw), print_fn=None)
    conf = confidence(conn, "BRSSZ")
    conn.close()
    assert conf["paired_windows"] == 0
    assert conf["confidence"] == 0.45  # base recente, sem bônus


def test_confidence_v1_cap_is_untouched():
    """Guarda da fórmula v1: bônus para em 0.35 → confiança teto 0.80."""
    import tempfile

    tmp = tempfile.mkdtemp()
    oracle = os.path.join(tmp, "o.duckdb")
    c = duckdb.connect(oracle)
    c.execute(ANTAQ_DDL)
    c.execute(
        "INSERT INTO antaq_validation VALUES ('BRPNG', 2026, 'jan', 200, 195, 100.0, 50.0, 200.0, 40.0, 180.0, '2026-01-01')"
    )
    c.execute("""
        CREATE TABLE calibration_pairs (
            port_id VARCHAR, observed_at DATE, waiting_vessels INTEGER,
            ao_largo INTEGER, esperados INTEGER, atracados INTEGER, source VARCHAR,
            antaq_espera_avg_h DOUBLE, antaq_espera_med_h DOUBLE,
            antaq_espera_p90_h DOUBLE, antaq_janela VARCHAR, matched INTEGER
        )
    """)
    c.execute(
        "INSERT INTO calibration_pairs (port_id, matched) VALUES ('BRPNG', 1)"
    )
    conf = confidence(c, "BRPNG")
    c.close()
    assert conf["paired_windows"] == 1
    assert conf["confidence"] == 0.52  # 0.45 + 0.07


def test_classification_thresholds():
    assert pp.classification_status(18, 0.80, 18) == pp.CALIBRATED
    assert pp.classification_status(20, 0.80, 25) == pp.CALIBRATED
    assert pp.classification_status(17, 0.80, 17) == pp.QUALIFIED  # <18 matched
    assert pp.classification_status(6, 0.72, 6) == pp.QUALIFIED
    assert pp.classification_status(5, 0.80, 5) == pp.LIMITED      # <6 matched
    assert pp.classification_status(2, 0.59, 4) == pp.LIMITED
    assert pp.classification_status(0, 0.45, 5) == pp.LIMITED      # ≥3 pares totais
    assert pp.classification_status(0, 0.45, 2) == pp.INSUFFICIENT
    assert pp.classification_status(0, 0.30, 0) == pp.INSUFFICIENT


def test_missing_raw_database_is_silent_noop(tmp_path):
    oracle = _oracle(tmp_path, {"BRPNG": (100.0, 50.0, 200.0)})
    conn = duckdb.connect(str(oracle))
    written = pp.register_pairs(
        conn, raw_path=str(tmp_path / "nao-existe.duckdb"), print_fn=None
    )
    conn.close()
    assert written == []


# ── Gate 0.6: guarda de frescor (observação velha ≠ observação de hoje) ──────

def test_stale_observation_produces_no_pair(tmp_path):
    """Ingestão falha deixa line-up velho: NÃO pode virar par 'de hoje'."""
    oracle = _oracle(tmp_path, {"BRPNG": (100.0, 50.0, 200.0)})
    raw = tmp_path / "raw.duckdb"
    c = duckdb.connect(str(raw))
    c.execute(RAW_DDL)
    c.execute(
        "INSERT INTO raw_port_lineup VALUES ('1','BRPNG','NAVIO','2026-10-03','AO_LARGO','GRANEL','AG','appa',50000.0,'2026-09-20 08:00:00')"
    )
    c.close()
    conn = duckdb.connect(str(oracle))
    written = pp.register_pairs(conn, raw_path=str(raw), print_fn=None, max_age_hours=6.0)
    conn.close()
    assert written == [], "observação de dias atrás não pode gerar par datado de hoje"
    conn = duckdb.connect(str(oracle), read_only=True)
    assert conn.execute("SELECT COUNT(*) FROM calibration_pairs").fetchone()[0] == 0
    conn.close()


def test_recent_observation_still_produces_pair(tmp_path):
    """Contraprova: dentro da janela de frescor, o par nasce normalmente."""
    from datetime import datetime, timedelta, timezone

    oracle = _oracle(tmp_path, {"BRPNG": (100.0, 50.0, 200.0)})
    recente = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    raw = tmp_path / "raw.duckdb"
    c = duckdb.connect(str(raw))
    c.execute(RAW_DDL)
    c.execute(
        f"INSERT INTO raw_port_lineup VALUES ('1','BRPNG','NAVIO','2026-10-03','AO_LARGO','GRANEL','AG','appa',50000.0,'{recente}')"
    )
    c.close()
    conn = duckdb.connect(str(oracle))
    written = pp.register_pairs(conn, raw_path=str(raw), print_fn=None, max_age_hours=6.0)
    conn.close()
    assert len(written) == 1
    assert written[0]["waiting_vessels"] == 1


# ── Gate 0.6: invariâncias do porto-alvo (script/calibration_report.py) ─────

def _report(port_id, matched, conf, status, live=True, antaq=True, newest_days=0, n=5):
    return {
        "ports": [
            {
                "port_id": port_id,
                "matched_windows": matched,
                "confidence": conf,
                "calibration_status": status,
                "pair_age_distribution": {"n": n, "newest_days": newest_days},
                "coverage": {"live_lineup": live, "antaq_history": antaq},
            }
        ]
    }


def test_gate06_check_passes_when_qualified():
    import scripts.calibration_report as cr

    report = _report("BRPNG", 6, 0.80, "QUALIFIED")
    assert cr.check_invariants(report) == []


def test_gate06_check_fails_on_each_invariant():
    import scripts.calibration_report as cr

    # hoje: 5 matched, conf 0.8, LIMITED → falha no matched e no status
    fails = cr.check_invariants(_report("BRPNG", 5, 0.80, "LIMITED"))
    assert any("matched=5" in f for f in fails)
    assert any("LIMITED" in f for f in fails)

    for kwargs, needle in (
        ({"conf": 0.59}, "confidence"),
        ({"newest_days": 3}, "ciclo diário"),
        ({"live": False}, "line-up vivo"),
        ({"antaq": False}, "janela ANTAQ"),
        ({"n": 0}, "menos de 2 pares"),
    ):
        base = dict(port_id="BRPNG", matched=6, conf=0.80, status="QUALIFIED")
        base.update(kwargs)
        fails = cr.check_invariants(_report(**base))
        assert any(needle in f for f in fails), f"{needle} não detectado: {fails}"


def test_gate06_check_reports_missing_target():
    import scripts.calibration_report as cr

    fails = cr.check_invariants(_report("BRRIO", 6, 0.80, "QUALIFIED"), target_port="BRPNG")
    assert fails == ["BRPNG ausente no relatório"]
