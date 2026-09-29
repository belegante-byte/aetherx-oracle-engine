"""Testes do fluxo de monetização Stripe (checkout / webhook / fulfillment).

Cobre o P0: a chave paga precisa cair no MESMO cofre JSON que
`authenticate_client` lê, com entrega idempotente por external_id (session_id).

Isolamento: monkyepatch do cofre (KEYS_FILE/META_FILE) para tmpdir e dos
objetos stripe para evitar chamadas de rede.
"""
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.runtime import access
from src.api import monetization

client = TestClient(app)


def _fresh_cofre(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "KEYS_FILE", tmp_path / "m2m_keys.json")
    monkeypatch.setattr(access, "META_FILE", tmp_path / "m2m_keys_meta.json")
    monkeypatch.setattr(access, "VALID_M2M_KEYS", {})
    monkeypatch.setattr(access, "_KEY_META", {})
    monkeypatch.setattr(access, "_KEY_PLANS", {})
    monkeypatch.setattr(access, "_PAYMENT_GRANTS", {})
    monkeypatch.setattr(access, "_KEY_LEVELS", {})
    access.load_keys_from_disk()


def _fake_session(payment_status="paid", session_id="cs_test_123", email="trader@corp.com.br"):
    return {
        "id": session_id,
        "payment_status": payment_status,
        "status": "complete" if payment_status == "paid" else "open",
        "customer_email": email,
        "customer_details": {"email": email},
        "metadata": {"product": "gp5_monthly_m2m", "plan": "GP5_ENTERPRISE"},
    }


@pytest.fixture(autouse=True)
def _monkeypatch_stripe(tmp_path, monkeypatch):
    _fresh_cofre(tmp_path, monkeypatch)
    import stripe

    monkeypatch.setattr(stripe, "api_key", "sk_test_fake")
    monkeypatch.setattr(monetization, "STRIPE_WEBHOOK_SECRET", "whsec_test")


def test_checkout_requires_email():
    resp = client.get("/checkout/gp5-monthly")
    assert resp.status_code == 422


def test_checkout_without_stripe_key_returns_503(monkeypatch):
    import stripe

    monkeypatch.setattr(stripe, "api_key", None)
    resp = client.get("/checkout/gp5-monthly", params={"email": "trader@corp.com.br"})
    assert resp.status_code == 503


def test_checkout_creates_subscription_redirect(monkeypatch):
    import stripe

    calls = {}

    class FakeSession:
        url = "https://checkout.stripe.com/c/pay/x"

    def fake_create(**kwargs):
        calls.update(kwargs)
        return FakeSession()

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)
    resp = client.get("/checkout/gp5-monthly", params={"email": "trader@corp.com.br"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == FakeSession.url
    assert calls["mode"] == "subscription"
    assert calls["line_items"][0]["price_data"]["unit_amount"] == 500000
    assert calls["line_items"][0]["price_data"]["recurring"] == {"interval": "month"}
    assert calls["customer_email"] == "trader@corp.com.br"
    assert "{CHECKOUT_SESSION_ID}" in calls["success_url"]
    assert "/m2m-keys/fulfillment" in calls["success_url"]


def test_fulfillment_grants_key_idempotently(monkeypatch):
    import stripe

    session = _fake_session()
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda sid: session)

    r1 = client.get("/m2m-keys/fulfillment", params={"session_id": session["id"]})
    r2 = client.get("/m2m-keys/fulfillment", params={"session_id": session["id"]})
    assert r1.status_code == 200
    assert r2.status_code == 200

    import re

    tokens = re.findall(r"gp5_enterprise_[0-9a-f]{16}", r1.text)
    assert len(set(tokens)) >= 1, "a página deve exibir a chave"
    key = tokens[0]
    assert key in r2.text, "segunda chamada deve devolver a MESMA chave"

    ctx = access.authenticate_client(f"Bearer {key}", product="gp5")
    assert ctx.access_mode == "authenticated"
    assert ctx.has_permission("decision.*")

    assert access.get_paid_key_for_email(session["customer_email"]) == key


def test_webhook_grants_key_and_is_idempotent(monkeypatch):
    import stripe

    session = _fake_session(session_id="cs_test_webhook")
    event = {"type": "checkout.session.completed", "data": {"object": session}}
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda *a, **k: event)

    r1 = client.post("/webhook/stripe", content=b"{}", headers={"stripe-signature": "sig1"})
    r2 = client.post("/webhook/stripe", content=b"{}", headers={"stripe-signature": "sig1"})
    assert r1.status_code == 200
    assert r2.status_code == 200

    gp = access._PAYMENT_GRANTS
    assert gp.get(session["id"]) is not None
    assert gp[session["id"]] in access._KEY_PLANS
    assert len({v for v in gp.values()}) == len(gp), "uma chave por external_id"


def test_webhook_bad_signature_returns_400(monkeypatch):
    import stripe

    def bad_construct(*a, **k):
        raise ValueError("bad signature")

    monkeypatch.setattr(stripe.Webhook, "construct_event", bad_construct)
    resp = client.post("/webhook/stripe", content=b"{}", headers={"stripe-signature": "bad"})
    assert resp.status_code == 400


def test_fulfillment_unpaid_does_not_grant(monkeypatch):
    import stripe

    session = _fake_session(payment_status="unpaid", session_id="cs_test_unpaid")
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda sid: session)

    resp = client.get("/m2m-keys/fulfillment", params={"session_id": session["id"]})
    assert resp.status_code == 200
    assert "não confirmado" in resp.text
    assert session["id"] not in access._PAYMENT_GRANTS


def test_webhook_and_fulfillment_share_one_key(monkeypatch):
    import stripe

    # Cenário real: webhook e fulfillment disparam para a mesma sessão.
    session = _fake_session(session_id="cs_test_shared")
    event = {"type": "checkout.session.completed", "data": {"object": session}}
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda *a, **k: event)
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda sid: session)

    webhook_resp = client.post("/webhook/stripe", content=b"{}", headers={"stripe-signature": "sig"})
    assert webhook_resp.status_code == 200

    import re

    fulfillment_resp = client.get("/m2m-keys/fulfillment", params={"session_id": session["id"]})
    tokens = re.findall(r"gp5_enterprise_[0-9a-f]{16}", fulfillment_resp.text)
    assert tokens, "fulfillment deve expor a chave"
    assert tokens[0] == access._PAYMENT_GRANTS[session["id"]], "uma única chave por assinatura"


# -----------------------------------------------------------------------------
# Escada de preços (paridade com a prateleira): Pro US$ 499/mo, Enterprise
# US$ 5.000/mo, intervalos month/year, e degradação 503 sem Stripe.
# -----------------------------------------------------------------------------

def _capture_create(monkeypatch):
    import stripe

    calls = {}

    class FakeSession:
        url = "https://checkout.stripe.com/c/pay/x"

    def fake_create(**kwargs):
        calls.update(kwargs)
        return FakeSession()

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)
    return calls


def test_checkout_default_remains_enterprise_monthly(monkeypatch):
    calls = _capture_create(monkeypatch)
    client.get("/checkout/gp5-monthly", params={"email": "ceo@corp.com.br"}, follow_redirects=False)
    price = calls["line_items"][0]["price_data"]
    assert price["unit_amount"] == 500000
    assert price["recurring"] == {"interval": "month"}
    assert calls["metadata"] == {"product": "gp5_monthly_m2m", "plan": "enterprise"}


def test_checkout_pro_plan_price(monkeypatch):
    calls = _capture_create(monkeypatch)
    client.get("/checkout/gp5-monthly", params={"email": "ceo@corp.com.br", "plan": "pro"}, follow_redirects=False)
    price = calls["line_items"][0]["price_data"]
    assert price["unit_amount"] == 49900
    assert "GP5 Pro" in price["product_data"]["name"]
    assert calls["metadata"]["plan"] == "pro"


def test_checkout_pro_alias_route(monkeypatch):
    calls = _capture_create(monkeypatch)
    client.get("/checkout/gp5-pro", params={"email": "ceo@corp.com.br"}, follow_redirects=False)
    assert calls["line_items"][0]["price_data"]["unit_amount"] == 49900


def test_checkout_enterprise_annual(monkeypatch):
    calls = _capture_create(monkeypatch)
    client.get("/checkout/gp5-monthly", params={"email": "ceo@corp.com.br", "interval": "year"}, follow_redirects=False)
    price = calls["line_items"][0]["price_data"]
    assert price["unit_amount"] == 5000000
    assert price["recurring"] == {"interval": "year"}


def test_checkout_pro_annual_discount(monkeypatch):
    calls = _capture_create(monkeypatch)
    client.get("/checkout/gp5-pro", params={"email": "ceo@corp.com.br", "interval": "year"}, follow_redirects=False)
    assert calls["line_items"][0]["price_data"]["unit_amount"] == 499000  # 10 meses


def test_checkout_invalid_plan_returns_400(monkeypatch):
    calls = _capture_create(monkeypatch)
    resp = client.get("/checkout/gp5-monthly", params={"email": "ceo@corp.com.br", "plan": "gold"}, follow_redirects=False)
    assert resp.status_code == 400
    assert not calls, "nenhuma session Stripe deve ser criada"


def test_checkout_invalid_interval_returns_400(monkeypatch):
    calls = _capture_create(monkeypatch)
    resp = client.get("/checkout/gp5-monthly", params={"email": "ceo@corp.com.br", "interval": "week"}, follow_redirects=False)
    assert resp.status_code == 400
    assert not calls


def test_checkout_pro_without_stripe_key_returns_503(monkeypatch):
    import stripe

    monkeypatch.setattr(stripe, "api_key", None)
    resp = client.get("/checkout/gp5-pro", params={"email": "ceo@corp.com.br"})
    assert resp.status_code == 503


# -----------------------------------------------------------------------------
# Coexistência (governança 2026-09-29): REST de produto aceita proxy-secret
# (RapidAPI) OU chave paga via Bearer (Stripe). Trial NÃO abre a REST paga.
# -----------------------------------------------------------------------------
import os

os.environ.setdefault("RAPIDAPI_PROXY_SECRET", "test-secret")

RECT = {"port_id": "brssz"}


def test_rest_product_without_secret_and_without_key_401():
    assert TestClient(app).get("/v1/port-risk", params=RECT).status_code == 401


def test_rest_product_with_paid_key_bearer_200(tmp_path, monkeypatch):
    from src.runtime.access import register_paid_m2m_key

    monkeypatch.setattr(access, "KEYS_FILE", tmp_path / "m2m_keys.json")
    monkeypatch.setattr(access, "META_FILE", tmp_path / "m2m_keys_meta.json")
    monkeypatch.setattr(access, "VALID_M2M_KEYS", {})
    monkeypatch.setattr(access, "_KEY_META", {})
    monkeypatch.setattr(access, "_KEY_PLANS", {})
    monkeypatch.setattr(access, "_PAYMENT_GRANTS", {})
    monkeypatch.setattr(access, "_KEY_LEVELS", {})
    access.load_keys_from_disk()

    key = register_paid_m2m_key("Trader", "ceo@corp.com.br", "Acme", "evt_coexist_1")
    resp = TestClient(app).get(
        "/v1/gp5/fiscal-routing",
        params={"intended_port_id": "BRSSZ", "commodity": "FERTILIZANTES"},
        headers={"Authorization": f"Bearer {key}"},
    )
    assert resp.status_code == 200
    assert resp.json()["schema_version"] == "fiscal-routing.v1"


def test_rest_product_with_trial_key_still_401(tmp_path, monkeypatch):
    # Trial dá acesso MCP, mas NÃO abre a REST de produto (só proxy-secret ou
    # chave paga). Regressão do fluxo pré-1.3.0 em que trial abria /v1/gp5/.
    from src.runtime.access import register_m2m_key

    monkeypatch.setattr(access, "KEYS_FILE", tmp_path / "m2m_keys.json")
    monkeypatch.setattr(access, "META_FILE", tmp_path / "m2m_keys_meta.json")
    monkeypatch.setattr(access, "VALID_M2M_KEYS", {})
    monkeypatch.setattr(access, "_KEY_META", {})
    monkeypatch.setattr(access, "_KEY_PLANS", {})
    monkeypatch.setattr(access, "_PAYMENT_GRANTS", {})
    monkeypatch.setattr(access, "_KEY_LEVELS", {})
    access.load_keys_from_disk()

    key = register_m2m_key("Agent", "agent@corp.com.br", "Acme")
    resp = TestClient(app).get(
        "/v1/gp5/fiscal-routing",
        params={"intended_port_id": "BRSSZ", "commodity": "FERTILIZANTES"},
        headers={"Authorization": f"Bearer {key}"},
    )
    assert resp.status_code == 401