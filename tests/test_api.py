import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

os.environ.setdefault("RAPIDAPI_PROXY_SECRET", "test-secret")
TEST_SECRET = os.environ["RAPIDAPI_PROXY_SECRET"]

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.engine.risk_model import calculate_port_risk
from src.api.metrics import record_tool_call, metrics_snapshot, _tools, _ports, _recent_events, _lock


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

def test_control_tower_requires_secret():
    resp = TestClient(app).get("/internal/control-tower")
    assert resp.status_code == 401


def test_control_tower_returns_html_with_metrics():
    resp = client.get("/internal/control-tower")
    assert resp.status_code == 200
    body = resp.text
    assert "AETHER-X CONTROL TOWER" in body
    assert "SYSTEM" in body
    assert "TOP TOOLS" in body
    assert "DISCOVERY" in body
    assert "DATA QUALITY" in body


def test_metrics_snapshot_has_control_tower_fields():
    s = metrics_snapshot()
    for field in ("requests_total", "mcp_calls", "mcp_errors", "error_rate",
                  "top_tools", "top_ports", "recent_events"):
        assert field in s


def test_record_tool_call_populates_tower():
    with _lock:
        _tools.clear()
        _ports.clear()
        _recent_events.clear()
    record_tool_call("get_port_risk", port_id="BRPNG", ok=True, latency_ms=5)
    s = metrics_snapshot()
    assert s["mcp_calls"] >= 1
    assert s["mcp_errors"] == 0
    assert ("get_port_risk", 1) in s["top_tools"]
    assert ("BRPNG", 1) in s["top_ports"]
    kinds = [e["kind"] for e in s["recent_events"]]
    assert "tool_call" in kinds and "port_query" in kinds


def test_record_tool_call_tracks_error():
    with _lock:
        _tools.clear()
        _ports.clear()
        _recent_events.clear()
    before_errors = metrics_snapshot()["mcp_errors"]
    record_tool_call("get_port_trend", port_id="BRSSZ", ok=False, latency_ms=3)
    s = metrics_snapshot()
    assert s["mcp_errors"] == before_errors + 1
    assert s["top_tools"][0][0] == "get_port_trend"


def test_record_rapidapi_call_tracks_paid_plan():
    from src.api.metrics import record_rapidapi_call, metrics_snapshot, _paid_plans, _paid_users, _lock
    with _lock:
        _paid_plans.clear()
        _paid_users.clear()
    record_rapidapi_call("PRO", "alice_dev")
    record_rapidapi_call("ULTRA", "bob_co")
    record_rapidapi_call("BASIC", "free_user")
    record_rapidapi_call(None, None)
    s = metrics_snapshot()
    assert s["paid_plans"] == {"PRO": 1, "ULTRA": 1}
    assert s["paid_user_count"] == 2
    assert "alice_dev" in s["paid_users"] and "bob_co" in s["paid_users"]


def test_metrics_persistence_roundtrip(tmp_path):
    from src.api import metrics as m
    state_path = tmp_path / "metrics_state.json"
    m._tools.clear(); m._ports.clear(); m._paid_plans.clear(); m._paid_users.clear()
    m._mcp_total = 0; m._mcp_errors = 0
    m.record_tool_call("get_port_risk", port_id="BRPNG", ok=True, latency_ms=4)
    m.record_rapidapi_call("PRO", "test_payer")
    # persiste
    old_path = m._STATE_PATH
    m._STATE_PATH = str(state_path)
    m._persist_now()
    # zera e recarrega
    m._tools.clear(); m._ports.clear(); m._paid_plans.clear(); m._paid_users.clear()
    m._mcp_total = 0; m._mcp_errors = 0
    m._load_state()
    m._STATE_PATH = old_path
    s = m.metrics_snapshot()
    assert ("get_port_risk", 1) in s["top_tools"]
    assert ("BRPNG", 1) in s["top_ports"]
    assert s["paid_plans"] == {"PRO": 1}
    assert "test_payer" in s["paid_users"]
    assert s["mcp_calls"] == 1


def test_tool_call_tracks_consumer():
    from src.api.metrics import (record_tool_call, metrics_snapshot, set_current_machine,
                                 _tools, _ports, _mcp_consumers, _mcp_consumer_ips, _lock)
    with _lock:
        _tools.clear(); _ports.clear(); _mcp_consumers.clear(); _mcp_consumer_ips.clear()
    set_current_machine("abcd1234")
    record_tool_call("get_port_risk", port_id="BRPNG", ok=True, latency_ms=3)
    set_current_machine("abcd1234")
    record_tool_call("get_port_risk", port_id="BRSSZ", ok=True, latency_ms=2)
    set_current_machine("efgh5678")
    record_tool_call("get_port_trend", port_id="CNSHA", ok=True, latency_ms=4)
    s = metrics_snapshot()
    assert s["mcp_consumer_count"] == 2  # duas máquinas distintas executaram tool
    calls = s["mcp_consumers"]["calls_by_machine"]
    assert calls["abcd1234"] == 2
    assert calls["efgh5678"] == 1
    assert s["mcp_calls"] >= 3


def test_funnel_tracks_machine_stages():
    from src.api import metrics as m
    from src.api.metrics import _MACHINE_STAGES, _MACHINE_CALLS, _MACHINE_FIRST, _MACHINE_LAST, _lock
    with _lock:
        _MACHINE_STAGES.clear(); _MACHINE_CALLS.clear(); _MACHINE_FIRST.clear(); _MACHINE_LAST.clear()
    m._mark_stage("faaa11", "discovery")
    m._mark_stage("faaa11", "mcp_connect")
    m.set_current_machine("faaa11")
    m.record_tool_call("get_port_risk", port_id="BRPNG", ok=True)
    m._mark_stage("faaa11", "repeat_transport")
    m._mark_stage("fbbb22", "discovery")
    s = m.metrics_snapshot()
    f = s["funnel"]
    assert f["discovery"] == 2
    assert f["mcp_connect"] == 1
    assert f["tool_call"] == 1
    assert f["repeat_transport"] == 1
    assert f["repeat_tool"] == 0
    assert f["paid"] == 0
    ids = {x["id"] for x in s["machines"]}
    assert "faaa11" in ids
    stages = {x["id"]: x["stages"] for x in s["machines"]}
    assert "tool_call" in stages["faaa11"]


def test_repeat_tool_detects_product_retention():
    from src.api import metrics as m
    from src.api.metrics import _MACHINE_STAGES, _MACHINE_TOOL_TS, _MACHINE_TOOL_PORTS, _lock
    with _lock:
        _MACHINE_STAGES.clear(); _MACHINE_TOOL_TS.clear(); _MACHINE_TOOL_PORTS.clear()
    # executa tool agora
    m.set_current_machine("rpt1111")
    m.record_tool_call("get_port_risk", port_id="BRPNG", ok=True)
    # simula retorno em janela posterior (força o ts antigo)
    with _lock:
        _MACHINE_TOOL_TS["rpt1111"] = [int(__import__("time").time()) - 1000]
    m.set_current_machine("rpt1111")
    m.record_tool_call("get_port_risk", port_id="BRPNG", ok=True)
    s = m.metrics_snapshot()
    assert s["funnel"]["tool_call"] == 1  # 1 máquina executou tool
    assert s["funnel"]["repeat_tool"] == 1  # e essa máquina retornou p/ tool
    stages = {x["id"]: x["stages"] for x in s["machines"]}
    assert "repeat_tool" in stages["rpt1111"]
    assert any(
        x.get("ports", {}).get("BRPNG") for x in s["machines"] if x["id"] == "rpt1111"
    )


def test_payload_has_decision_signal():
    data = calculate_port_risk("BRPNG")
    sig = data.get("signal")
    assert sig is not None
    for field in ("level", "live_observation", "queue_vessels", "decision_implication", "as_of"):
        assert field in sig
    assert sig["level"] in ("HIGH OPERATIONAL PRESSURE", "ELEVATED OPERATIONAL PRESSURE", "MODERATE / LOW PRESSURE")
    assert "decision_implication" in sig


def test_mcp_tool_descriptions_are_decision_oriented():
    from src.api.mcp_app import mcp
    import asyncio
    async def _get():
        tools = await mcp.list_tools()
        return tools if not hasattr(tools, "tools") else tools.tools
    tools = asyncio.run(_get())
    by_name = {t.name: (t.description or "") for t in tools}
    assert "Use this tool when a decision depends" in by_name.get("get_port_risk", "")
    assert "Compare CURRENT congestion" in by_name.get("get_ports_risk", "")
    assert "SYNTHETIC projection" in by_name.get("get_port_trend", "")
