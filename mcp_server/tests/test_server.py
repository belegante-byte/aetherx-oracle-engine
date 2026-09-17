import asyncio

import httpx

from aetherx_mcp import server


def _mock_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        port = request.url.params.get("port_id", "")
        return httpx.Response(
            200,
            json={
                "port_id": port,
                "port_name": "Santos",
                "country": "Brasil",
                "congestion_score": 0.78,
                "eta_delay_days": 1.6,
                "waiting_vessels": 12,
                "freight_volatility_index": 0.42,
                "updated_at": "2026-09-17 15:46:53",
            },
        )

    return httpx.MockTransport(handler)


def test_list_supported_ports_returns_fifteen() -> None:
    ports = server.list_supported_ports()
    assert len(ports) == 15
    assert any(p["port_id"] == "BRSSZ" for p in ports)


def test_get_port_risk_normalizes_locode(monkeypatch) -> None:
    transport = _mock_transport()
    monkeypatch.setattr(
        server, "_client", lambda: httpx.AsyncClient(transport=transport)
    )
    result = asyncio.run(server.get_port_risk(" brssz "))
    assert result["port_id"] == "BRSSZ"
    assert result["congestion_score"] == 0.78


def test_get_ports_risk_batch(monkeypatch) -> None:
    transport = _mock_transport()
    monkeypatch.setattr(
        server, "_client", lambda: httpx.AsyncClient(transport=transport)
    )
    results = asyncio.run(server.get_ports_risk(["BRSSZ", "CNSHA", "NLRTM"]))
    assert [r["port_id"] for r in results] == ["BRSSZ", "CNSHA", "NLRTM"]


def test_rapidapi_headers_only_when_key_present(monkeypatch) -> None:
    monkeypatch.delenv("RAPIDAPI_KEY", raising=False)
    assert server._headers() == {}
    monkeypatch.setenv("RAPIDAPI_KEY", "secret")
    headers = server._headers()
    assert headers["X-RapidAPI-Key"] == "secret"
    assert "X-RapidAPI-Host" in headers
