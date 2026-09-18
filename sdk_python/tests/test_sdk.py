import asyncio
import os
import sys
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
import pytest
import requests
import responses

from aetherx import OracleClient, PortRisk, PortTrend

HOST = "aether-x-port-congestion-oracle.p.rapidapi.com"
URL = f"https://{HOST}/v1/port-risk"
TREND_URL = f"https://{HOST}/v1/port-trend"
PORTS_RISK_URL = f"https://{HOST}/v1/ports-risk"

SAMPLE = {
    "port_id": "BRSSZ",
    "port_name": "Santos",
    "country": "Brasil",
    "congestion_score": 0.78,
    "eta_delay_days": 1.6,
    "waiting_vessels": 12,
    "freight_volatility_index": 0.42,
    "estimated_daily_demurrage_usd": 63200,
    "updated_at": "2026-09-17 15:46:53",
}

FALLBACK = {
    "port_id": "ZZZ99",
    "port_name": "Unknown Port (Global Estimate)",
    "country": "Global",
    "congestion_score": 0.45,
    "eta_delay_days": 1.0,
    "waiting_vessels": 6,
    "freight_volatility_index": 0.35,
    "estimated_daily_demurrage_usd": 50000,
    "updated_at": "2026-09-17 15:47:19",
}

TREND = {
    "port_id": "BRSSZ",
    "port_name": "Santos",
    "country": "Brasil",
    "trend": "estável",
    "congestion_score": 0.78,
    "projection": {
        "h24": {
            "congestion_score": 0.76,
            "eta_delay_days": 1.56,
            "estimated_daily_demurrage_usd": 62400,
        },
        "h48": {
            "congestion_score": 0.75,
            "eta_delay_days": 1.54,
            "estimated_daily_demurrage_usd": 61800,
        },
        "h72": {
            "congestion_score": 0.74,
            "eta_delay_days": 1.52,
            "estimated_daily_demurrage_usd": 61200,
        },
    },
    "updated_at": "2026-09-17 15:46:53",
}


def make_client() -> OracleClient:
    return OracleClient(api_key="test-key")


def test_empty_api_key_raises():
    with pytest.raises(ValueError):
        OracleClient(api_key="")


def test_empty_port_id_raises():
    with pytest.raises(ValueError):
        make_client().get_port_risk("")


@responses.activate
def test_get_port_risk_parses_response():
    responses.add(responses.GET, URL, json=SAMPLE, status=200)

    risk = make_client().get_port_risk("BRSSZ")

    assert isinstance(risk, PortRisk)
    assert risk.port_id == "BRSSZ"
    assert risk.port_name == "Santos"
    assert risk.country == "Brasil"
    assert risk.congestion_score == 0.78
    assert risk.eta_delay_days == 1.6
    assert risk.waiting_vessels == 12
    assert risk.freight_volatility_index == 0.42
    assert risk.estimated_daily_demurrage_usd == 63200
    assert risk.updated_at == "2026-09-17 15:46:53"


@responses.activate
def test_sends_rapidapi_headers_and_query_param():
    responses.add(responses.GET, URL, json=SAMPLE, status=200)

    make_client().get_port_risk("BRSSZ")

    request = responses.calls[0].request
    assert request.headers["x-rapidapi-key"] == "test-key"
    assert request.headers["x-rapidapi-host"] == HOST
    assert "port_id=BRSSZ" in request.url


@responses.activate
def test_fallback_payload_parses():
    responses.add(responses.GET, URL, json=FALLBACK, status=200)

    risk = make_client().get_port_risk("ZZZ99")

    assert risk.country == "Global"
    assert risk.congestion_score == 0.45
    assert risk.waiting_vessels == 6


@responses.activate
def test_http_error_is_raised():
    responses.add(responses.GET, URL, json={"detail": "boom"}, status=500)

    with pytest.raises(requests.HTTPError):
        make_client().get_port_risk("BRSSZ")


@responses.activate
def test_get_port_trend_parses_response():
    responses.add(responses.GET, TREND_URL, json=TREND, status=200)

    trend = make_client().get_port_trend("BRSSZ")

    assert isinstance(trend, PortTrend)
    assert trend.port_id == "BRSSZ"
    assert trend.trend == "estável"
    assert trend.congestion_score == 0.78
    assert trend.projection["h24"].congestion_score == 0.76
    assert trend.projection["h72"].estimated_daily_demurrage_usd == 61200


@responses.activate
def test_get_port_trend_sends_query_param():
    responses.add(responses.GET, TREND_URL, json=TREND, status=200)

    make_client().get_port_trend("brssz")

    request = responses.calls[0].request
    assert request.headers["x-rapidapi-key"] == "test-key"
    assert "port_id=brssz" in request.url


@responses.activate
def test_get_ports_risk_sync_batch():
    results = [
        {**SAMPLE, "port_id": "BRSSZ", "port_name": "Santos"},
        {**SAMPLE, "port_id": "CNSHA", "port_name": "Shanghai"},
    ]
    responses.add(
        responses.GET, PORTS_RISK_URL, json={"results": results}, status=200
    )

    ports = make_client().get_ports_risk(["BRSSZ", "CNSHA"])

    assert len(ports) == 2
    assert [p.port_id for p in ports] == ["BRSSZ", "CNSHA"]

    request = responses.calls[0].request
    query = parse_qs(urlparse(request.url).query)
    assert query["port_ids"] == ["BRSSZ,CNSHA"]


def test_get_ports_risk_sync_empty_list():
    assert make_client().get_ports_risk([]) == []


def _patch_httpx(monkeypatch, handler):
    real_async_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


def test_get_port_risk_async_parses(monkeypatch):
    def handler(request):
        assert request.headers["x-rapidapi-key"] == "test-key"
        assert request.headers["x-rapidapi-host"] == HOST
        return httpx.Response(200, json=SAMPLE)

    _patch_httpx(monkeypatch, handler)

    risk = asyncio.run(make_client().get_port_risk_async("BRSSZ"))

    assert risk.port_name == "Santos"
    assert risk.waiting_vessels == 12


def test_get_ports_risk_async_gathers_multiple(monkeypatch):
    def handler(request):
        port_id = dict(request.url.params)["port_id"]
        payload = {**SAMPLE, "port_id": port_id, "port_name": f"Port {port_id}"}
        return httpx.Response(200, json=payload)

    _patch_httpx(monkeypatch, handler)

    results = asyncio.run(
        make_client().get_ports_risk_async(["BRSSZ", "CNSHA", "NLRTM"])
    )

    assert len(results) == 3
    assert [r.port_id for r in results] == ["BRSSZ", "CNSHA", "NLRTM"]


def test_get_ports_risk_async_empty_list():
    assert asyncio.run(make_client().get_ports_risk_async([])) == []
