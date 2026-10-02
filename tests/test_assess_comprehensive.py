import pytest
from src.api.mcp_app import assess_logistics_disruption

def test_missing_pci_and_vqpm_keys(monkeypatch):
    import src.engine.analytics
    monkeypatch.setattr(src.engine.analytics, "calculate_pci", lambda *a, **kw: {"pci_score": None})
    monkeypatch.setattr(src.engine.analytics, "calculate_vqpm", lambda *a, **kw: {"trend": "unknown_value"})

    res = assess_logistics_disruption("NLRTM")
    assert res["status"] == "partial"
    assert any("Warning: Assessment is incomplete" in r or "Assessment inconclusive" in r for r in res["risk_assessment"]["risks"])

def test_irdi_failure_with_corridor(monkeypatch):
    import src.engine.analytics
    monkeypatch.setattr(src.engine.analytics, "calculate_irdi", lambda *a, **kw: {"irdi_score": "not_a_number"})
    res = assess_logistics_disruption("NLRTM", corridor_id="NLRTM")
    assert res["status"] == "partial"

def test_static_source_no_proceed():
    res = assess_logistics_disruption("NLRTM")
    assert res["data_quality"]["classification"] in ["reference", "modeled"]
    imps = [d["implication"] for d in res.get("decision_implications", [])]
    assert "Proceed with planned logistics." not in imps

def test_live_source_but_signal_none(monkeypatch):
    import src.engine.risk_model
    def mock_risk(*a, **k):
        return {
            "eta_delay_days": 1,
            "congestion_score": 0.1,
            "data_source": "live:mock",
            "decision_grade": "decision",
            "signal": None
        }
    monkeypatch.setattr(src.engine.risk_model, "calculate_port_risk", mock_risk)
    res = assess_logistics_disruption("MOCK")
    assert res["data_quality"]["classification"] in ["reference", "modeled"]

def test_invalid_horizons():
    with pytest.raises(TypeError, match="must be an integer"):
        assess_logistics_disruption("NLRTM", horizon_hours=24.5)
    with pytest.raises(TypeError, match="must be an integer"):
        assess_logistics_disruption("NLRTM", horizon_hours=True)
    with pytest.raises(ValueError, match="must be between 1 and 168"):
        assess_logistics_disruption("NLRTM", horizon_hours=0)
    with pytest.raises(ValueError, match="must be between 1 and 168"):
        assess_logistics_disruption("NLRTM", horizon_hours=200)

    res = assess_logistics_disruption("NLRTM", horizon_hours="48")
    assert res["subject"]["effective_forecast_days"] == 2

def test_demurrage_math():
    res = assess_logistics_disruption("BRSSZ")
    # Fetch impact
    hypo = next((h["hypothesis"] for h in res["impact_hypotheses"] if "Demurrage exposure" in h["hypothesis"]), None)
    assert hypo is not None
    # Ensure it's not 'unknown'
    assert "unknown" not in hypo
    # The actual string must contain the exact computed number
    from src.engine.analytics import calculate_pci, DEMURRAGE_BASE_USD_DAY
    pci_res = calculate_pci("BRSSZ")
    delay = pci_res["components"]["avg_delay_days"]
    score = pci_res["pci_score"]

    if score >= 70.0:
        expected = int((delay + 1.5) * DEMURRAGE_BASE_USD_DAY)
    elif score >= 40.0:
        expected = int(delay * DEMURRAGE_BASE_USD_DAY)
    else:
        expected = int(max(0, delay - 1.0) * DEMURRAGE_BASE_USD_DAY)

    assert str(expected) in hypo

def test_timestamps():
    res = assess_logistics_disruption("NLRTM")
    assert "generated_at" in res
    assert "as_of" not in res
    # provenance observed_at shouldn't equal generated_at blindly if missing, but it might be missing
    for p in res["provenance"]:
        assert "observed_at" in p or "generated_at" in p

def test_risk_risks_partial_incomplete(monkeypatch):
    import src.engine.risk_model
    def mock_risk(*a, **k):
        return {"eta_delay_days": 5.0, "congestion_score": 0.9, "data_source": "static"}
    monkeypatch.setattr(src.engine.risk_model, "calculate_port_risk", mock_risk)

    import src.engine.analytics
    monkeypatch.setattr(src.engine.analytics, "calculate_pci", lambda *a, **kw: {})
    res = assess_logistics_disruption("MOCK")

    risks = res["risk_assessment"]["risks"]
    assert "Operational delay observed at port." in risks
    assert any("Warning: Assessment is incomplete" in r for r in risks)
    assert res["status"] == "partial"


def test_live_source_invalid_decision_grade(monkeypatch):
    import src.engine.risk_model
    monkeypatch.setattr(src.engine.risk_model, "calculate_port_risk", lambda *a, **k: {
        "eta_delay_days": 1, "congestion_score": 0.1,
        "data_source": "live:mock", "decision_grade": "reference",
        "as_of": "2026-09-30T10:00:00+00:00",
        "signal": {"live_observation": True}
    })
    res = assess_logistics_disruption("MOCK")
    assert res["data_quality"]["classification"] in ["reference", "modeled"]

def test_live_source_no_timestamp(monkeypatch):
    import src.engine.risk_model
    monkeypatch.setattr(src.engine.risk_model, "calculate_port_risk", lambda *a, **k: {
        "eta_delay_days": 1, "congestion_score": 0.1,
        "data_source": "live:mock", "decision_grade": "decision",
        "as_of": None,
        "signal": {"live_observation": True}
    })
    res = assess_logistics_disruption("MOCK")
    assert res["data_quality"]["classification"] in ["reference", "modeled"]

def test_live_source_obsolete_data(monkeypatch):
    import src.engine.risk_model
    monkeypatch.setattr(src.engine.risk_model, "calculate_port_risk", lambda *a, **k: {
        "eta_delay_days": 1, "congestion_score": 0.1,
        "data_source": "live:mock", "decision_grade": "decision",
        "as_of": "2020-01-01T10:00:00+00:00",
        "signal": {"live_observation": True}
    })
    res = assess_logistics_disruption("MOCK")
    assert res["data_quality"]["classification"] in ["reference", "modeled"]

def test_malformed_returns(monkeypatch):
    import src.engine.risk_model
    monkeypatch.setattr(src.engine.risk_model, "calculate_port_risk", lambda *a, **k: []) # not a dict
    res = assess_logistics_disruption("MOCK")
    assert res["status"] == "insufficient_data"

def test_live_source_future_timestamp(monkeypatch):
    import src.engine.risk_model
    monkeypatch.setattr(src.engine.risk_model, "calculate_port_risk", lambda *a, **k: {
        "eta_delay_days": 1, "congestion_score": 0.1,
        "data_source": "live:mock", "decision_grade": "decision",
        "as_of": "2099-01-01T10:00:00+00:00",
        "signal": {"live_observation": True}
    })
    res = assess_logistics_disruption("MOCK")
    # Future timestamp must be rejected as NOT fresh -> should fallback to static/modeled
    assert res["data_quality"]["classification"] in ["reference", "modeled"]

def test_live_source_positive_path(monkeypatch):
    import src.engine.risk_model
    import src.engine.analytics
    from datetime import datetime, timezone

    now_ts = datetime.now(timezone.utc).isoformat()

    monkeypatch.setattr(src.engine.risk_model, "calculate_port_risk", lambda *a, **k: {
        "eta_delay_days": 0.1, "congestion_score": 0.1, "data_source": "live:mock", "decision_grade": "decision",
        "as_of": now_ts, "signal": {"live_observation": True}
    })
    monkeypatch.setattr(src.engine.analytics, "calculate_pci", lambda *a, **kw: {"pci_score": 10.0, "data_source": "live:mock", "as_of": now_ts})
    monkeypatch.setattr(src.engine.analytics, "calculate_vqpm", lambda *a, **kw: {"current_vessel_queue": 10, "vqpm_predictions": {"day_1": {"predicted_vessel_queue": 10}}, "data_source": "live:mock", "as_of": now_ts})

    from src.api.mcp_app import assess_logistics_disruption
    res = assess_logistics_disruption("MOCK")
    assert res["data_quality"]["classification"] in ["reference", "modeled", "live_verified", "live_unverified_time", "live_stale"]
    imps = [d["implication"] for d in res.get("decision_implications", [])]
    assert "No significant disruption detected in the available live observations." in imps
def test_mixed_source_proceed_caution(monkeypatch):
    import src.engine.risk_model
    import src.engine.analytics
    from datetime import datetime, timezone

    now_ts = datetime.now(timezone.utc).isoformat()

    monkeypatch.setattr(src.engine.risk_model, "calculate_port_risk", lambda *a, **k: {
        "eta_delay_days": 0.1, "congestion_score": 0.1, "data_source": "live:mock", "decision_grade": "decision",
        "as_of": now_ts, "signal": {"live_observation": True}
    })
    monkeypatch.setattr(src.engine.analytics, "calculate_pci", lambda *a, **kw: {"pci_score": 10.0, "data_source": "modeled", "as_of": now_ts})
    monkeypatch.setattr(src.engine.analytics, "calculate_vqpm", lambda *a, **kw: {"current_vessel_queue": 10, "vqpm_predictions": {"day_1": {"predicted_vessel_queue": 10}}, "data_source": "predictive_model", "evaluated_at": now_ts})

    from src.api.mcp_app import assess_logistics_disruption
    res = assess_logistics_disruption("MOCK")
    assert res["data_quality"]["classification"] in ["reference", "modeled", "live_verified", "live_unverified_time", "live_stale"]
    imps = [d["implication"] for d in res.get("decision_implications", [])]
    assert "Proceed with caution." in imps
    assert "Proceed with planned logistics." not in imps
def test_nan_inf_values(monkeypatch):
    import src.engine.analytics
    import src.engine.risk_model
    import math

    monkeypatch.setattr(src.engine.risk_model, "calculate_port_risk", lambda *a, **k: {"eta_delay_days": math.nan, "congestion_score": 0.5})
    res = assess_logistics_disruption("MOCK")
    assert res["status"] == "insufficient_data"

    monkeypatch.setattr(src.engine.risk_model, "calculate_port_risk", lambda *a, **k: {"eta_delay_days": 0.1, "congestion_score": 0.5})
    monkeypatch.setattr(src.engine.analytics, "calculate_pci", lambda *a, **kw: {"pci_score": math.inf})
    res = assess_logistics_disruption("MOCK")
    assert res["status"] == "partial"


def test_m2m_identity_comprehensive(monkeypatch):
    import src.api.metrics as metrics
    from src.api.mcp_app import assess_logistics_disruption
    import time

    metrics._MACHINE_TOOL_TS.clear()
    metrics._MACHINE_STAGES.clear()

    # 1. Identidade anônima
    metrics.current_machine_id.set(None)
    assess_logistics_disruption("NLRTM")
    assess_logistics_disruption("BRSSZ")
    assert None not in metrics._MACHINE_TOOL_TS
    assert None not in metrics._MACHINE_STAGES

    # 2. Chamadas de tool vs. chamadas de transporte
    metrics.current_machine_id.set("mock_machine_3")

    # Simula transporte separadamente
    metrics._mark_stage("mock_machine_3", "repeat_transport")

    # Uma chamada real
    assess_logistics_disruption("NLRTM")
    assert len(metrics._MACHINE_TOOL_TS["mock_machine_3"]) == 1
    assert "repeat_tool" not in metrics._MACHINE_STAGES.get("mock_machine_3", set())
    assert "repeat_transport" in metrics._MACHINE_STAGES.get("mock_machine_3", set())

    # Força a TS da primeira tool no passado para bater a janela TOOL_REPEAT_WINDOW (300s)
    metrics._MACHINE_TOOL_TS["mock_machine_3"][0] = int(time.time()) - 400

    # Segunda chamada real -> gera repeat_tool no _record_tool_ts
    assess_logistics_disruption("NLRTM")
    assert "repeat_tool" in metrics._MACHINE_STAGES.get("mock_machine_3", set())

def test_missing_component_prevents_all_live(monkeypatch):
    import src.engine.risk_model
    import src.engine.analytics
    from datetime import datetime, timezone

    now_ts = datetime.now(timezone.utc).isoformat()

    monkeypatch.setattr(src.engine.risk_model, "calculate_port_risk", lambda *a, **k: {
        "eta_delay_days": 0.1, "congestion_score": 0.1, "data_source": "live:mock", "decision_grade": "decision",
        "as_of": now_ts, "signal": {"live_observation": True}
    })
    monkeypatch.setattr(src.engine.analytics, "calculate_pci", lambda *a, **kw: {"pci_score": 10.0, "data_source": "live:mock", "as_of": now_ts})

    # Simula VQPM falhando e não retornando nada (ou levantando exceção)
    monkeypatch.setattr(src.engine.analytics, "calculate_vqpm", lambda *a, **kw: {})

    from src.api.mcp_app import assess_logistics_disruption
    res = assess_logistics_disruption("MOCK")
    # Faltou VQPM, status cai pra partial, all_live não pode ser True
    assert res["status"] == "partial"
    assert res["data_quality"]["classification"] in ["reference", "modeled", "live_verified", "live_unverified_time", "live_stale"]
    imps = [d["implication"] for d in res.get("decision_implications", [])]
    assert "Proceed with planned logistics." not in imps

def test_boolean_rejection(monkeypatch):
    import src.engine.risk_model
    from src.api.mcp_app import assess_logistics_disruption
    monkeypatch.setattr(src.engine.risk_model, "calculate_port_risk", lambda *a, **k: {
        "eta_delay_days": False, "congestion_score": 0.1
    })
    res = assess_logistics_disruption("MOCK")
    assert res["status"] == "insufficient_data"


def test_metrics_repeat_tool_exact():
    import src.api.metrics as metrics
    metrics._MACHINE_TOOL_TS.clear()
    metrics._MACHINE_STAGES.clear()
    if hasattr(metrics, '_MACHINE_TOOL_NAMES'): metrics._MACHINE_TOOL_NAMES.clear()

    mid = "test_repeat_mid"
    metrics.current_machine_id.set(mid)

    # Call tool A
    metrics.record_tool_call("tool_A")
    assert "repeat_tool" not in metrics._MACHINE_STAGES.get(mid, set())

    # Call tool B
    metrics.record_tool_call("tool_B")
    assert "repeat_tool" not in metrics._MACHINE_STAGES.get(mid, set())

    # Call tool A again
    metrics.record_tool_call("tool_A")
    assert "repeat_tool" in metrics._MACHINE_STAGES.get(mid, set())
