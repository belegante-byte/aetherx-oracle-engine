import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

os.environ.setdefault("RAPIDAPI_PROXY_SECRET", "test-secret")
TEST_SECRET = os.environ["RAPIDAPI_PROXY_SECRET"]

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.engine.risk_model import calculate_port_risk


client = TestClient(app, headers={"X-RapidAPI-Proxy-Secret": TEST_SECRET})


def test_health_check():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Aether-X Port Congestion Oracle" in resp.text
    assert "https://aetherx.aether-grid.io/mcp" in resp.text
    assert 'href="/docs"' in resp.text
    assert 'href="/llms.txt"' in resp.text
    assert 'href="/port-congestion-api"' in resp.text
    assert 'href="/santos-port-congestion-api"' in resp.text
    assert 'href="/port-congestion-python"' in resp.text
    assert 'href="/mcp-page"' in resp.text
    assert "Live Snapshot" in resp.text
    assert "data_source" in resp.text
    assert "BRSSZ" in resp.text
    assert "NLRTM" in resp.text
    assert "estimated_daily_demurrage_usd" in resp.text
    assert "Raw JSON" in resp.text


def test_content_pages_are_public_and_render():
    for path, marker in [
        ("/mcp-page", "Available tools"),
        ("/port-congestion-api", "Congestion score (0.0–1.0)"),
        ("/santos-port-congestion-api", "Latin America"),
        ("/port-congestion-python", "pip install --upgrade aetherx-oracle"),
    ]:
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert "text/html" in resp.headers["content-type"], path
        assert marker in resp.text, path


def test_sitemap_lists_all_content_pages():
    resp = client.get("/sitemap.xml")
    assert resp.status_code == 200
    assert "application/xml" in resp.headers["content-type"]
    assert resp.text.count("<url>") == 24


def test_robots_txt():
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "Sitemap: https://aetherx.aether-grid.io/sitemap.xml" in resp.text


def test_port_detail_pages_live_for_all_monitored_ports():
    from src.api.content_pages import PORT_METAS

    for meta in PORT_METAS:
        resp = client.get(f"/port-congestion-{meta['slug']}")
        assert resp.status_code == 200, meta["slug"]
        assert "text/html" in resp.headers["content-type"], meta["slug"]
        assert meta["port_name"] in resp.text, meta["slug"]
        assert meta["port_id"] in resp.text, meta["slug"]
        assert "congestion_score" in resp.text, meta["slug"]
        assert 'rel="canonical"' in resp.text, meta["slug"]
        assert f'/port-congestion-{meta["slug"]}' in resp.text, meta["slug"]


def test_port_detail_unknown_slug_404():
    resp = client.get("/port-congestion-nao-existe")
    assert resp.status_code == 404


def test_port_risk_known_port():
    resp = client.get("/v1/port-risk", params={"port_id": "brssz"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["port_id"] == "BRSSZ"
    assert body["port_name"] == "Santos"
    assert body["country"] == "Brasil"
    assert body["estimated_daily_demurrage_usd"] > 0
    assert body["updated_at"]
    assert body["as_of"] == body["updated_at"]
    # Santos agora é alimentado por fonte viva (painel de operações da CODESP).
    assert body["data_source"].startswith("live:")
    assert body["data_source_label"]
    assert "live" in body and body["live"]["atracados"] > 0


def test_port_risk_static_seed_for_unlived_port():
    resp = client.get("/v1/port-risk", params={"port_id": "aedxb"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["port_id"] == "AEDXB"
    assert body["data_source"] == "static_reference_seed"
    assert body["data_source_label"]
    assert body["congestion_score"] == 0.50


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
    assert body["estimated_daily_demurrage_usd"] == 50000
    assert body["as_of"]
    assert body["data_source"] == "static_reference_seed"


def test_port_risk_missing_param():
    resp = client.get("/v1/port-risk")
    assert resp.status_code == 422


def test_engine_returns_all_required_fields():
    data = calculate_port_risk("CNSHA")
    expected_fields = {
        "port_id", "port_name", "country", "congestion_score",
        "eta_delay_days", "waiting_vessels", "freight_volatility_index",
        "estimated_daily_demurrage_usd", "updated_at", "as_of",
        "data_source", "data_source_label",
    }
    assert expected_fields <= set(data.keys())


def test_openapi_contains_response_schema():
    schema = app.openapi()
    assert "PortRiskResponse" in schema["components"]["schemas"]
    assert "/v1/port-risk" in schema["paths"]
    example = schema["paths"]["/v1/port-risk"]["get"]["responses"]["200"]["content"]["application/json"]["example"]
    assert example["data_source"].startswith("live:") or example["data_source"] == "static_reference_seed"


def test_qingdao_new_port_supported():
    resp = client.get("/v1/port-risk", params={"port_id": "CNTAO"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["port_name"] == "Qingdao"
    assert body["country"] == "China"
    assert body["estimated_daily_demurrage_usd"] == 56000


def test_bpng_calibrated_fields_exposed_via_api():
    """Regressão: PortRiskResponse (Pydantic) filtrava os campos calibrados.

    O engine gera historical_expected_wait_h/p90/expected_demurrage/confidence,
    mas o modelo de resposta os descartava silenciosamente. Verifica que o
    endpoint /v1/port-risk os expõe para o porto calibrado (BRPNG).
    """
    resp = client.get("/v1/port-risk", params={"port_id": "BRPNG"})
    assert resp.status_code == 200
    body = resp.json()
    calibrados = {
        "historical_expected_wait_h",
        "p90_wait_h",
        "expected_demurrage_usd",
        "p90_demurrage_usd",
        "confidence",
        "paired_windows",
        "fonte",
        "semantica",
    }
    assert calibrados <= set(body.keys())
    if body.get("confidence") is not None:
        assert body["confidence"] >= 0
        assert body["expected_demurrage_usd"] > 0


def test_bpng_live_waiting_is_real_queue():
    """Regressão: waiting_vessels deve ser a fila real (ao_largo), não a soma
    com esperados/programados (chegadas futuras)."""
    resp = client.get("/v1/port-risk", params={"port_id": "BRPNG"})
    assert resp.status_code == 200
    body = resp.json()
    live = body.get("live") or {}
    if live.get("ao_largo") is not None:
        assert body["waiting_vessels"] == live["ao_largo"]


def test_port_trend_projection():
    resp = client.get("/v1/port-trend", params={"port_id": "brssz"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["port_id"] == "BRSSZ"
    assert body["trend"] in {"acelerando", "estável", "descongestionando"}
    assert body["data_source"] == "synthetic_projection"
    assert body["as_of"]
    assert set(body["projection"].keys()) == {"h24", "h48", "h72"}
    point = body["projection"]["h24"]
    assert set(point.keys()) == {
        "congestion_score", "eta_delay_days", "estimated_daily_demurrage_usd",
    }


def test_guard_rejects_without_secret():
    resp = TestClient(app).get("/v1/port-risk", params={"port_id": "brssz"})
    assert resp.status_code == 401
    assert "X-RapidAPI-Proxy-Secret" in resp.json()["detail"]


def test_guard_accepts_valid_secret():
    resp = client.get("/v1/port-risk", params={"port_id": "brssz"})
    assert resp.status_code == 200


def test_guard_exempts_public_paths():
    public = TestClient(app)
    assert public.get("/").status_code == 200
    assert public.get("/docs").status_code == 200
    assert public.get("/redoc").status_code == 200
    assert public.get("/openapi.json").status_code == 200
    assert public.get("/openapi.rapidapi.json").status_code == 200
    assert public.get("/llms.txt").status_code == 200
    assert public.get("/terms").status_code == 200
    assert public.get("/sitemap.xml").status_code == 200
    assert public.get("/robots.txt").status_code == 200
    assert public.get("/mcp-page").status_code == 200
    assert public.get("/port-congestion-api").status_code == 200
    assert public.get("/santos-port-congestion-api").status_code == 200
    assert public.get("/port-congestion-python").status_code == 200
    assert public.get("/port-congestion-santos").status_code == 200
    assert public.get("/public/ports").status_code == 200


def test_guard_exempts_verification_files():
    """Arquivos de verificação Google/Bing são públicos (sem secret) e a rota
    genérica não captura páginas normais nem aceita arquivos arbitrários."""
    public = TestClient(app)
    # arquivo de verificação ausente → 404 (rota existe, é pública, mas sem arquivo)
    assert public.get("/google0123456789abcdef0123456789abcdef01234567.html").status_code == 404
    assert public.get("/BingSiteAuth.xml").status_code == 404
    # arquivo arbitrário não é isento do guard → 401 (não é verificação válida)
    assert public.get("/foo.html").status_code == 401
    # páginas normais não são capturadas pela rota genérica
    assert public.get("/mcp-page").status_code == 200
    assert public.get("/santos-port-congestion-api").status_code == 200
    assert public.get("/openapi.rapidapi.json").status_code == 200


def test_guard_exempts_mcp():
    with TestClient(app) as c:
        resp = c.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200


def test_ports_risk_batch():
    resp = client.get("/v1/ports-risk", params={"port_ids": "brssz,CNSHA,NLRTM"})
    assert resp.status_code == 200
    body = resp.json()
    assert [r["port_id"] for r in body["results"]] == ["BRSSZ", "CNSHA", "NLRTM"]
    assert body["results"][0]["estimated_daily_demurrage_usd"] > 0
    # BRSSZ vivo; demais seguem o seed de referência.
    assert body["results"][0]["data_source"].startswith("live:")
    assert body["results"][1]["data_source"] == "static_reference_seed"
    assert body["results"][2]["data_source"] == "static_reference_seed"


def test_ports_risk_batch_limit():
    too_many = ",".join(["AEDXB"] * 21)
    resp = client.get("/v1/ports-risk", params={"port_ids": too_many})
    assert resp.status_code == 400


def test_openapi_enriched_metadata():
    schema = app.openapi()
    assert "/v1/ports-risk" in schema["paths"]
    op = schema["paths"]["/v1/port-risk"]["get"]
    assert op["summary"] == "Get port congestion risk for a single port"
    assert op["description"]
    assert "401" in op["responses"]
    example = op["responses"]["200"]["content"]["application/json"]["example"]
    assert example["port_id"] == "BRSSZ"
    assert schema["components"]["schemas"]["PortsRiskResponse"]


def test_metrics_classify():
    from src.api.metrics import _classify

    assert _classify("/mcp", "some-agent/1.0") == "mcp"
    assert _classify("/v1/port-risk", "python-requests/2.32") == "rest"
    assert _classify("/openapi.json", "curl/8.6") == "discovery"
    assert _classify("/port-congestion-santos", "Mozilla/5.0 Googlebot/2.1") == "bot"
    assert _classify("/mcp", "mcpbeat/0.1 liveness check") == "bot"
    assert _classify("/mcp", "SentinelOracle/0.1 liveness-only") == "bot"
    assert _classify("/", "Mozilla/5.0 (Macintosh; Intel Mac OS X)") is None
    assert _classify("/health", "curl/8.6") is None
    assert _classify("/v1/port-risk", "belegante-aetherx/1.0") is None


def test_metrics_tracks_repeat_machines():
    from src.api import metrics

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/port-risk",
        "headers": [(b"user-agent", b"python-requests/2.32")],
        "client": ("203.0.113.7", 1000),
    }
    metrics.record_http(scope)
    metrics.record_http(dict(scope))
    snap = metrics.metrics_snapshot()
    assert "repeat_machines" in snap
    assert "second_call_rate" in snap
    assert snap["repeat_machines"].get("rest", 0) >= 1
    assert snap["second_call_rate"]["rest"] > 0.0


def test_internal_metrics_protected():
    pub = TestClient(app)
    assert pub.get("/internal/metrics").status_code == 401


def test_internal_metrics_returns_snapshot():
    resp = client.get("/internal/metrics")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("uptime_seconds", "total", "unique_machines", "top_paths"):
        assert key in body


def test_public_ports_feed():
    pub = TestClient(app)
    resp = pub.get("/public/ports")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 19
    assert len(body["results"]) == 19
    first = body["results"][0]
    for key in (
        "port_id", "port_name", "country", "congestion_score",
        "eta_delay_days", "waiting_vessels", "freight_volatility_index",
        "estimated_daily_demurrage_usd", "updated_at", "as_of",
        "data_source", "data_source_label",
    ):
        assert key in first
    # Feed é misto: portos BR vivos + seed de referência para os demais.
    data_sources = {r["data_source"] for r in body["results"]}
    assert "static_reference_seed" in data_sources
    assert any(ds.startswith("live:") for ds in data_sources)