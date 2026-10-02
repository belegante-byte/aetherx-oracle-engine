"""Provenance & data_quality contract tests.

These tests validate the new provenance layer introduced in feature/provenance-schema:

- APPA / Santos / Lachmann / SILOG → live_unverified_time (source_observed_at is null)
- ShipInfo AIS → live_verified (source_observed_at is explicit)
- seed / calibrated reference → reference
- source_observed_at=null → age_seconds=null, freshness=unknown
- stale (>48h) explicit timestamp → live_stale
- No oracle.duckdb mutation: all mocked.
"""

import json
import pytest
from datetime import datetime, timezone, timedelta

# --------------------------------------------------------------------- helpers

def _make_prov(source: str, q: str, obs_at=None, ret_at=None) -> str:
    """Build a JSON-serialised provenance list as stored in port_metrics."""
    ret_at = ret_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return json.dumps([{
        "source": source,
        "source_url": "https://example.com",
        "source_observed_at": obs_at,
        "retrieved_at": ret_at,
        "source_timestamp_quality": q,
    }])


def _risk_stub(provenance_json: str, data_source: str = "live:mock") -> dict:
    """Minimal calculate_port_risk return value for monkeypatching."""
    return {
        "eta_delay_days": 1.5,
        "congestion_score": 0.6,
        "data_source": data_source,
        "decision_grade": "decision",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "signal": {"live_observation": True},
        "provenance": provenance_json,
    }


# ------------------------------------------------------------------- APPA / BR ports

def test_appa_connector_yields_live_unverified_time(monkeypatch):
    """APPA does not provide source_observed_at → classification must be live_unverified_time."""
    import src.engine.risk_model as rm
    monkeypatch.setattr(rm, "calculate_port_risk",
                        lambda *a, **k: _risk_stub(_make_prov("APPA", "unknown", obs_at=None)))

    from src.api.mcp_app import assess_logistics_disruption
    res = assess_logistics_disruption("BRPNG")
    dq = res["data_quality"]
    assert dq["classification"] == "live_unverified_time"
    assert dq["source_observed_at"] is None
    assert dq["age_seconds"] is None
    assert dq["freshness"] == "unknown"


def test_santos_connector_yields_live_unverified_time(monkeypatch):
    """Santos SPA does not provide source_observed_at → live_unverified_time."""
    import src.engine.risk_model as rm
    monkeypatch.setattr(rm, "calculate_port_risk",
                        lambda *a, **k: _risk_stub(_make_prov("Santos_Painel", "unknown", obs_at=None)))

    from src.api.mcp_app import assess_logistics_disruption
    res = assess_logistics_disruption("BRSSZ")
    dq = res["data_quality"]
    assert dq["classification"] == "live_unverified_time"
    assert dq["source_observed_at"] is None
    assert dq["age_seconds"] is None


def test_lachmann_connector_yields_live_unverified_time(monkeypatch):
    """Lachmann XLS does not provide source_observed_at → live_unverified_time."""
    import src.engine.risk_model as rm
    monkeypatch.setattr(rm, "calculate_port_risk",
                        lambda *a, **k: _risk_stub(_make_prov("Lachmann", "unknown", obs_at=None)))

    from src.api.mcp_app import assess_logistics_disruption
    res = assess_logistics_disruption("BRPNG")
    dq = res["data_quality"]
    assert dq["classification"] == "live_unverified_time"


# ------------------------------------------------------------------- ShipInfo (AIS)

def test_shipinfo_fresh_explicit_yields_live_verified(monkeypatch):
    """ShipInfo provides snapshot_ts → source_timestamp_quality=explicit → live_verified."""
    import src.engine.risk_model as rm
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    monkeypatch.setattr(rm, "calculate_port_risk",
                        lambda *a, **k: _risk_stub(_make_prov("ShipInfo", "explicit", obs_at=now_iso)))

    from src.api.mcp_app import assess_logistics_disruption
    res = assess_logistics_disruption("NLRTM")
    dq = res["data_quality"]
    assert dq["classification"] == "live_verified"
    assert dq["source_observed_at"] == now_iso
    assert dq["age_seconds"] is not None
    assert dq["age_seconds"] < 60   # captured moments ago
    assert dq["freshness"] == "fresh"


def test_shipinfo_stale_explicit_yields_live_stale(monkeypatch):
    """ShipInfo snapshot 50 hours old → live_stale."""
    import src.engine.risk_model as rm
    old_iso = (datetime.now(timezone.utc) - timedelta(hours=50)).strftime("%Y-%m-%dT%H:%M:%SZ")
    monkeypatch.setattr(rm, "calculate_port_risk",
                        lambda *a, **k: _risk_stub(_make_prov("ShipInfo", "explicit", obs_at=old_iso)))

    from src.api.mcp_app import assess_logistics_disruption
    res = assess_logistics_disruption("NLRTM")
    dq = res["data_quality"]
    assert dq["classification"] == "live_stale"
    assert dq["freshness"] == "stale"
    assert dq["age_seconds"] > 48 * 3600


# ------------------------------------------------------------------- Seed / Reference

def test_seed_provenance_yields_reference(monkeypatch):
    """calibrated_reference_seed → classification=reference."""
    import src.engine.risk_model as rm
    monkeypatch.setattr(rm, "calculate_port_risk",
                        lambda *a, **k: _risk_stub(
                            _make_prov("seed", "unknown", obs_at=None),
                            data_source="calibrated_reference_seed"
                        ))

    from src.api.mcp_app import assess_logistics_disruption
    res = assess_logistics_disruption("CNSHA")
    dq = res["data_quality"]
    assert dq["classification"] == "reference"


# ------------------------------------------------------------------- null timestamp contract

def test_null_source_observed_at_never_produces_age_seconds(monkeypatch):
    """When source_observed_at is null, age_seconds must be null — never datetime.now()."""
    import src.engine.risk_model as rm
    monkeypatch.setattr(rm, "calculate_port_risk",
                        lambda *a, **k: _risk_stub(_make_prov("APPA", "unknown", obs_at=None)))

    from src.api.mcp_app import assess_logistics_disruption
    res = assess_logistics_disruption("BRPNG")
    dq = res["data_quality"]
    assert dq["age_seconds"] is None, (
        "age_seconds must be null when source_observed_at is null — "
        "datetime.now() must NOT be substituted."
    )


# ------------------------------------------------------------------- no oracle.duckdb touched

def test_no_oracle_mutation_in_provenance_tests():
    """Guard: none of the mocked tests should have written to data/oracle.duckdb."""
    import os
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--name-only", "data/oracle.duckdb"],
        cwd="/Users/AETHER - X",
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "", (
        "data/oracle.duckdb must not be modified by provenance tests."
    )
