"""Testes unitários e de integração para o motor estatístico e rotas REST /v1/gp5/*."""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.engine.analytics import (
    calculate_pci,
    calculate_cdr,
    calculate_vqpm,
    calculate_irdi,
    calculate_scdew,
)

client = TestClient(app)


def test_pci_model_calculation():
    res = calculate_pci("SGSIN")
    assert res["port_id"] == "SGSIN"
    assert 0 <= res["pci_score"] <= 100
    assert res["pci_level"] in ("HIGH CONGESTION", "MODERATE CONGESTION", "LOW CONGESTION / NORMAL")
    assert "freight_rate_impact" in res["economic_impact"]
    assert "modeled_demurrage_exposure_usd" in res["economic_impact"]


def test_cdr_model_calculation():
    res = calculate_cdr("HORMUZ")
    assert res["chokepoint_id"] == "HORMUZ"
    assert 0 <= res["cdr_score"] <= 100
    assert "cdr_level" in res
    assert "economic_impact" in res
    assert "war_risk_insurance_premium_delta" in res["economic_impact"]


def test_vqpm_model_calculation():
    res = calculate_vqpm("CNSHA", forecast_horizon_days=7)
    assert res["port_id"] == "CNSHA"
    assert len(res["vqpm_predictions"]) == 7
    assert "day_1" in res["vqpm_predictions"]


def test_irdi_model_calculation():
    res = calculate_irdi("NLRTM")
    assert res["hub_id"] == "NLRTM"
    assert 0 <= res["irdi_score"] <= 100
    assert "intermodal_status" in res


def test_scdew_model_calculation():
    res = calculate_scdew("BRPNG", "CNTAO", "HORMUZ")
    assert "BRPNG -> CNTAO" in res["corridor"]
    assert 0 <= res["scdew_score"] <= 100
    assert "warning_level" in res
    assert "recommendation" in res


def test_rest_pci_endpoint():
    resp = client.get("/v1/gp5/pci", params={"port_id": "SGSIN"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["port_id"] == "SGSIN"
    assert "pci_score" in data


def test_rest_cdr_endpoint():
    resp = client.get("/v1/gp5/cdr", params={"chokepoint_id": "HORMUZ"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["chokepoint_id"] == "HORMUZ"
    assert "cdr_score" in data


def test_rest_vqpm_endpoint():
    resp = client.get("/v1/gp5/vqpm", params={"port_id": "CNSHA", "horizon_days": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["vqpm_predictions"]) == 5


def test_rest_irdi_endpoint():
    resp = client.get("/v1/gp5/irdi", params={"identifier": "NLRTM"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["hub_id"] == "NLRTM"


def test_rest_scdew_endpoint():
    resp = client.get("/v1/gp5/scdew", params={"origin_port": "BRPNG", "destination_port": "CNTAO"})
    assert resp.status_code == 200
    data = resp.json()
    assert "scdew_score" in data
