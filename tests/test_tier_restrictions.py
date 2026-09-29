"""Testes do controle de acesso por plano da REST paga (engenharia de produto).

Cobre, regra por regra, o contrato aprovado:
  1. Três níveis (trial | pro | enterprise) aplicados no servidor.
  2. Pro: dados dos 5 portos BR + série histórica (endpoint próprio, 90d).
  3. Enterprise: Pro + arbitragem de corredor + evidência ANTAQ.
  4. Slots = integrações concorrentes (não chamadas); quota independente.
  5. Credencial inválida/trial rejeitada SEM fallback; 403 com upgrade_hint.
  6. Medição registra o plano do cliente (sem expor chave).
  7. Integridade: nada de histórico anunciado como previsão.
"""
import re
import os

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.runtime import access
from src.runtime.access import (
    PLAN_ENTERPRISE,
    PLAN_PRO,
    PLAN_TRIAL,
    acquire_slot,
    authorization_gate,
    consume_call_quota,
    get_key_level,
    register_m2m_key,
    register_paid_m2m_key,
    release_slot,
)

# Mesma convenção dos demais módulos de teste: o RapidAPIGuard captura o
# proxy-secret na construção do stack (primeiro request do processo).
os.environ.setdefault("RAPIDAPI_PROXY_SECRET", "test-secret")
PROXY_SECRET = os.environ["RAPIDAPI_PROXY_SECRET"]
PROXY_HEADERS = {"X-RapidAPI-Proxy-Secret": PROXY_SECRET}

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_cofre(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "KEYS_FILE", tmp_path / "m2m_keys.json")
    monkeypatch.setattr(access, "META_FILE", tmp_path / "m2m_keys_meta.json")
    monkeypatch.setattr(access, "VALID_M2M_KEYS", {})
    monkeypatch.setattr(access, "_KEY_META", {})
    monkeypatch.setattr(access, "_KEY_PLANS", {})
    monkeypatch.setattr(access, "_PAYMENT_GRANTS", {})
    monkeypatch.setattr(access, "_KEY_LEVELS", {})
    access._SLOT_USED.clear()
    access._CALL_USED.clear()
    access.load_keys_from_disk()


def _pro_key(n: int = 1) -> str:
    return register_paid_m2m_key("Trader", f"trader{n}@corp.com.br", "Acme", f"evt_pro_{n}", level=PLAN_PRO)


def _ent_key(n: int = 1) -> str:
    return register_paid_m2m_key("Trader", f"ent{n}@corp.com.br", "Acme", f"evt_ent_{n}", level=PLAN_ENTERPRISE)


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


# ── Regra 1: níveis aplicados no servidor ────────────────────────────────────

def test_trial_key_never_opens_paid_rest():
    trial = register_m2m_key("Agent", "agent@corp.com.br", "Acme")
    assert get_key_level(trial) == PLAN_TRIAL
    for path, params in (
        ("/v1/port-risk", {"port_id": "BRSSZ"}),
        ("/v1/port-trend", {"port_id": "BRSSZ"}),
        ("/v1/port-history", {"port_id": "BRSSZ"}),
        ("/v1/verified-queue", {"port_id": "BRSSZ"}),
    ):
        resp = client.get(path, params=params, headers=_auth(trial))
        assert resp.status_code == 401, f"{path} não deveria abrir para trial"


def test_unknown_key_is_rejected_without_legacy_fallback():
    resp = client.get("/v1/port-risk", params={"port_id": "BRSSZ"}, headers=_auth("gp5_trial_nao_existe"))
    assert resp.status_code == 401
    body = resp.json()
    assert "detail" in body
    # Nenhumahint de acesso legado/anônimo na REST de produto.
    assert "anonymous" not in json_text(body)
    assert "legacy" not in json_text(body)


def json_text(body: dict) -> str:
    import json

    return json.dumps(body, ensure_ascii=False).lower()


def test_level_is_persisted_and_read_back(tmp_path):
    pro = _pro_key()
    ent = _ent_key()
    assert get_key_level(pro) == PLAN_PRO
    assert get_key_level(ent) == PLAN_ENTERPRISE
    assert re.match(r"^gp5_pro_[0-9a-f]{16}$", pro)
    assert re.match(r"^gp5_enterprise_[0-9a-f]{16}$", ent)
    meta = (tmp_path / "m2m_keys_meta.json").read_text(encoding="utf-8")
    assert access._META_LEVELS_KEY in meta
    assert pro in meta  # nível é persistido, não fica só em memória


def test_authorization_gate_matrix():
    pro = _pro_key()
    ent = _ent_key()
    assert authorization_gate(pro, "/v1/port-risk")["allowed"] is True
    assert authorization_gate(pro, "/v1/port-history")["allowed"] is True
    assert authorization_gate(pro, "/v1/gp5/fiscal-routing")["allowed"] is False
    assert authorization_gate(pro, "/v1/verified-queue")["required_plan"] == PLAN_ENTERPRISE
    assert authorization_gate(ent, "/v1/gp5/fiscal-routing")["allowed"] is True
    assert authorization_gate(ent, "/v1/verified-queue")["allowed"] is True


# ── Regra 2: Pro entrega os dados dos 5 portos BR + histórico ────────────────

def test_pro_key_reads_live_br_port_signals():
    key = _pro_key()
    resp = client.get("/v1/port-risk", params={"port_id": "BRSSZ"}, headers=_auth(key))
    assert resp.status_code == 200
    assert resp.headers["X-Plan"] == "pro"
    body = resp.json()
    assert body["data_source"].startswith("live:")  # fila de autoridade (5 portos BR)
    assert body["waiting_vessels"] is not None


def test_pro_key_reads_history_with_explicit_coverage():
    key = _pro_key()
    resp = client.get("/v1/port-history", params={"port_id": "BRSSZ", "days": 90}, headers=_auth(key))
    assert resp.status_code == 200
    body = resp.json()
    assert body["days_max"] == 90
    assert body["data_source"] in ("observed_history", "no_history_observations")
    assert isinstance(body["series"], list)
    # Integridade: histórico é rotulado como observado, nunca previsão.
    assert "history" in body["data_source_label"].lower() or "observac" in body["data_source_label"].lower()
    assert "coverage_note" in body


# ── Regra 3: Enterprise libera decisão + evidência ANTAQ ────────────────────

def test_pro_key_gets_403_with_upgrade_hint_on_enterprise_endpoints():
    key = _pro_key()
    for path, params in (
        ("/v1/gp5/fiscal-routing", {"intended_port_id": "BRSSZ", "commodity": "FERTILIZANTES"}),
        ("/v1/verified-queue", {"port_id": "BRSSZ"}),
    ):
        resp = client.get(path, params=params, headers=_auth(key))
        assert resp.status_code == 403, f"{path} deveria exigir enterprise"
        body = resp.json()
        assert body["code"] == "PLAN_REQUIRED"
        assert body["required_plan"] == "enterprise"
        assert body["plan"] == "pro"
        assert body["upgrade_hint"]
        assert "Enterprise" in body["upgrade_hint"]


def test_enterprise_key_unlocks_decision_endpoints():
    key = _ent_key()
    resp = client.get(
        "/v1/gp5/fiscal-routing",
        params={"intended_port_id": "BRSSZ", "commodity": "FERTILIZANTES"},
        headers=_auth(key),
    )
    assert resp.status_code == 200
    assert resp.headers["X-Plan"] == "enterprise"
    assert resp.json()["schema_version"] == "fiscal-routing.v1"


def test_enterprise_key_unlocks_antaq_verified_queue():
    key = _ent_key()
    resp = client.get("/v1/verified-queue", params={"port_id": "BRSSZ"}, headers=_auth(key))
    assert resp.status_code == 200
    assert resp.json()["port_id"] == "BRSSZ"


# ── Regra 4: slots são integrações concorrentes; quota é independente ─────────

def test_slot_is_concurrency_not_call_count():
    pro = _pro_key()
    ent = _ent_key()
    # Pro: 1 slot simultâneo. Chamadas em série liberam o slot.
    assert acquire_slot(pro) is True
    assert acquire_slot(pro) is False
    release_slot(pro)
    assert acquire_slot(pro) is True  # liberou → nova chamada cabe
    release_slot(pro)
    # Enterprise: 5 slots.
    for _ in range(5):
        assert acquire_slot(ent) is True
    assert acquire_slot(ent) is False
    for _ in range(5):
        release_slot(ent)
    assert acquire_slot(ent) is True
    release_slot(ent)


def test_pro_second_concurrent_call_hits_slot_limit():
    """Duas chamadas concorrentes com chave Pro: uma passa, a outra 429."""
    key = _pro_key()
    first = client.get("/v1/port-risk", params={"port_id": "BRSSZ"}, headers=_auth(key))
    assert first.status_code == 200
    # Slot liberado ao final da resposta → a segunda chamada seguinte passa.
    second = client.get("/v1/port-risk", params={"port_id": "BRPNG"}, headers=_auth(key))
    assert second.status_code == 200
    # Emulando duas requisições realmente simultâneas: o segundo slot é negado.
    assert acquire_slot(key) is True
    resp = client.get("/v1/port-risk", params={"port_id": "BRRIO"}, headers=_auth(key))
    assert resp.status_code == 429
    body = resp.json()
    assert body["code"] == "SLOT_LIMIT_EXCEEDED"
    assert body["slot_limit"] == 1
    assert body["upgrade_hint"]
    release_slot(key)


def test_call_quota_is_independent_of_slots(monkeypatch):
    monkeypatch.setattr(access, "DAILY_CALL_QUOTA", {PLAN_PRO: 3, PLAN_ENTERPRISE: 100})
    pro = _pro_key()
    results = [consume_call_quota(pro) for _ in range(4)]
    assert [r["allowed"] for r in results] == [True, True, True, False]
    assert results[-1]["limit"] == 3
    assert results[-1]["used"] == 3


def test_call_quota_exhaustion_returns_429(monkeypatch):
    monkeypatch.setattr(access, "DAILY_CALL_QUOTA", {PLAN_PRO: 1, PLAN_ENTERPRISE: 100})
    key = _pro_key()
    first = client.get("/v1/port-risk", params={"port_id": "BRSSZ"}, headers=_auth(key))
    assert first.status_code == 200
    assert first.headers["X-Call-Quota-Used"] == "1"
    assert first.headers["X-Call-Quota-Remaining"] == "0"
    second = client.get("/v1/port-risk", params={"port_id": "BRSSZ"}, headers=_auth(key))
    assert second.status_code == 429
    body = second.json()
    assert body["code"] == "CALL_QUOTA_EXCEEDED"
    assert body["limit"] == 1
    assert body["quota_resets"] == "midnight_utc"
    assert body["upgrade_hint"]


# ── Regra 5: compatibilidade do rail ativo (proxy do marketplace) ────────────

def test_rapidapi_proxy_secret_still_enterprise_equivalent(monkeypatch):
    """O rail ATIVO (RapidAPI) mede/cobra no marketplace: o proxy passa como
    enterprise-equivalente e não é barrado pelo tier gate local."""
    monkeypatch.setattr(access, "DAILY_CALL_QUOTA", {PLAN_PRO: 0, PLAN_ENTERPRISE: 100})
    for path, params in (
        ("/v1/port-risk", {"port_id": "BRSSZ"}),
        ("/v1/gp5/fiscal-routing", {"intended_port_id": "BRSSZ", "commodity": "FERTILIZANTES"}),
        ("/v1/verified-queue", {"port_id": "BRSSZ"}),
    ):
        resp = client.get(path, params=params, headers=PROXY_HEADERS)
        assert resp.status_code == 200, f"{path} via proxy-secret"


# ── Regra 6: medição com plano, sem vazar chave ─────────────────────────────

def test_usage_event_carries_plan_and_hides_key():
    from src.runtime.contracts.v1 import ClientContext
    from src.runtime.metering import record_usage

    key = _pro_key()
    ctx = access.authenticate_client(f"Bearer {key}", product="gp5")
    assert ctx.plan == PLAN_PRO
    event = record_usage(ctx, product="gp5", tool="/v1/port-risk", duration_ms=5, status_code=200)
    assert event.plan == PLAN_PRO
    assert key not in json_text({"tool": event.tool, "plan": event.plan, "client": event.client_id})


def test_legacy_context_has_no_plan():
    ctx = access.authenticate_client(None, product="gp5")
    assert ctx.access_mode == "legacy"
    assert ctx.plan == ""
