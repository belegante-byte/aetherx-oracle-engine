"""Regressão do gate de auth/quota no endpoint MCP remoto (/mcp).

POLÍTICA P1 (implementada no M2MGatewayMiddleware + mcp_quota):
  - tools de DECISÃO (charter/routing/corridor) exigem credencial M2M válida;
  - tools de OBSERVAÇÃO são gratuitas com quota diária por IP;
  - discovery (list_supported_ports) e provisioning (request_m2m_key) livres;
  - autenticados (Bearer válido) ignoram a quota.

O client compartilhado vem da fixture `mcp_client` (um único portal/lifespan;
o session manager do transporte MCP só roda uma vez por instância).
"""
import json

from src.api import mcp_quota
from src.api.metrics import metrics_snapshot
from src.runtime import access as access_mod


def _call(client, tool, args=None, headers=None, bearer=None, session=None):
    h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    if headers:
        h.update(headers)
    if bearer:
        h["Authorization"] = f"Bearer {bearer}"
    if session:
        h["mcp-session-id"] = session
    payload = {"jsonrpc": "2.0", "id": 11, "method": "tools/call",
               "params": {"name": tool, "arguments": args or {}}}
    return client.post("/mcp", json=payload, headers=h)


def _open_session(client):
    """Cria uma sessão MCP e devolve o mcp-session-id para as próximas chamadas."""
    payload = {"jsonrpc": "2.0", "id": 11, "method": "initialize",
               "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                          "clientInfo": {"name": "t", "version": "1"}}}
    r = client.post("/mcp", json=payload,
                    headers={"Accept": "application/json, text/event-stream",
                             "Content-Type": "application/json"})
    assert r.status_code == 200
    sid = r.headers.get("mcp-session-id")
    assert sid
    return sid


def _rpc(client, method, params=None, headers=None):
    h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    if headers:
        h.update(headers)
    payload = {"jsonrpc": "2.0", "id": 11, "method": method}
    if params is not None:
        payload["params"] = params
    return client.post("/mcp", json=payload, headers=h)


def _inject_key(key="quota_test_key", label="test_client"):
    access_mod.VALID_M2M_KEYS[key] = label
    return key


# ───────────────────────── unidade (mcp_quota) ─────────────────────────

def test_quota_helper_blocks_after_limit(monkeypatch):
    monkeypatch.setattr(mcp_quota, "OBSERVATION_QUOTA_PER_DAY", 2)
    ip = "9.9.0.10"
    assert mcp_quota.consume_observation_quota(ip) == (True, 1)
    assert mcp_quota.consume_observation_quota(ip) == (True, 0)
    assert mcp_quota.consume_observation_quota(ip) == (False, 0)


def test_quota_helper_tracks_remaining(monkeypatch):
    monkeypatch.setattr(mcp_quota, "OBSERVATION_QUOTA_PER_DAY", 5)
    ip = "9.9.0.11"
    mcp_quota.consume_observation_quota(ip)
    assert mcp_quota.observation_quota_remaining(ip) == 4


# ───────────────────────── interação HTTP (full app) ─────────────────────────

def test_decision_anon_denied_with_trial_hint(mcp_client):
    before = metrics_snapshot()["gates"]["decision_denied"]
    r = _call(mcp_client, "evaluate_charter_risk", {"port_id": "BRPNG"},
              {"X-Forwarded-For": "1.2.3.4"})
    assert r.status_code == 200
    body = json.loads(r.content)
    assert body["error"]["code"] == -32003
    assert "request_m2m_key" in body["error"]["message"]
    assert metrics_snapshot()["gates"]["decision_denied"] == before + 1


def test_observation_quota_exceeded(mcp_client, monkeypatch):
    monkeypatch.setattr(mcp_quota, "OBSERVATION_QUOTA_PER_DAY", 0)
    before = metrics_snapshot()["gates"]["quota_exceeded"]
    r = _call(mcp_client, "get_port_risk", {"port_id": "BRSSZ"},
              {"X-Forwarded-For": "1.2.3.5"})
    assert r.status_code == 200
    body = json.loads(r.content)
    assert body["error"]["code"] == -32004
    assert metrics_snapshot()["gates"]["quota_exceeded"] == before + 1


def test_trial_key_self_serve(mcp_client):
    before = metrics_snapshot()["gates"]["trial_keys_issued"]
    sid = _open_session(mcp_client)
    r = _call(mcp_client, "request_m2m_key",
              {"agent_name": "t", "organization": "acme"}, session=sid)
    assert r.status_code == 200
    assert "api_key" in r.text and "gp5_trial_" in r.text
    assert metrics_snapshot()["gates"]["trial_keys_issued"] == before + 1


def test_observation_anon_allowed_and_header_present(mcp_client):
    sid = _open_session(mcp_client)
    r = _call(mcp_client, "get_port_trend", {"port_id": "CNSHA"},
              {"X-Forwarded-For": "1.2.3.6"}, session=sid)
    assert r.status_code == 200
    assert r.headers.get("X-Observation-Quota-Left") is not None


def test_free_and_initialize_pass_through(mcp_client, monkeypatch):
    monkeypatch.setattr(mcp_quota, "OBSERVATION_QUOTA_PER_DAY", 0)
    sid = _open_session(mcp_client)
    r = _call(mcp_client, "list_supported_ports", {}, {"X-Forwarded-For": "1.2.3.7"}, session=sid)
    assert r.status_code == 200
    assert "-32003" not in r.text and "-32004" not in r.text


def test_authenticated_bypasses_quota_and_decision_gate(mcp_client):
    _inject_key()
    sid = _open_session(mcp_client)
    r = _call(mcp_client, "get_port_risk", {"port_id": "BRPNG"},
              {"X-Forwarded-For": "1.2.3.8"}, bearer="quota_test_key", session=sid)
    assert r.status_code == 200
    assert "-32004" not in r.text
    assert "-32003" not in r.text
    r2 = _call(mcp_client, "evaluate_routing_alternatives",
               {"port_a": "BRPNG", "port_b": "BRSSZ"},
               {"X-Forwarded-For": "1.2.3.8"}, bearer="quota_test_key", session=sid)
    assert r2.status_code == 200
    assert "-32003" not in r2.text