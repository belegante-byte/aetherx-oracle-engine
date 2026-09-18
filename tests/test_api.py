import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.engine.risk_model import calculate_port_risk


client = TestClient(app)


def test_health_check():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Aether-X Port Congestion Oracle" in resp.text
    assert "https://aether-x-oracle-production.up.railway.app/mcp" in resp.text
    assert 'href="/docs"' in resp.text
    assert 'href="/llms.txt"' in resp.text


def test_port_risk_known_port():
    resp = client.get("/v1/port-risk", params={"port_id": "brssz"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["port_id"] == "BRSSZ"
    assert body["port_name"] == "Santos"
    assert body["country"] == "Brasil"
    assert body["congestion_score"] == 0.78
    assert body["eta_delay_days"] == 1.6
    assert body["waiting_vessels"] == 12
    assert body["freight_volatility_index"] == 0.42
    assert body["updated_at"]


def test_port_risk_fallback_unknown_port():
    resp = client.get("/v1/port-risk", params={"port_id": "XXYYY"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["port_id"] == "XXYYY"
    assert body["port_name"] == "Unknown Port (Global Estimate)"
    assert body["country"] == "Global"
    assert body["congestion_score"] == 0.45
    assert body["waiting_vessels"] == 6
    assert body["freight_volatility_index"] == 0.35


def test_port_risk_missing_param():
    resp = client.get("/v1/port-risk")
    assert resp.status_code == 422


def test_engine_returns_all_required_fields():
    data = calculate_port_risk("CNSHA")
    expected_fields = {
        "port_id", "port_name", "country", "congestion_score",
        "eta_delay_days", "waiting_vessels", "freight_volatility_index", "updated_at"
    }
    assert expected_fields <= set(data.keys())


def test_openapi_contains_response_schema():
    schema = app.openapi()
    assert "PortRiskResponse" in schema["components"]["schemas"]
    assert "/v1/port-risk" in schema["paths"]