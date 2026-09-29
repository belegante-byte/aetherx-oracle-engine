import os
import stripe
import logging
from fastapi import APIRouter, Request, Header, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse

from src.runtime.access import register_paid_m2m_key

router = APIRouter(tags=["Monetization"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://aetherx.aether-grid.io")

# Escada de preços (Benchmark SupplyMaven API/MCP Pro = US$ 499/mo):
#   - Pro:       US$ 499/mo  (ou US$ 4.990/ano = 10 meses)
#   - Enterprise: US$ 5.000/mo (ou US$ 50.000/ano) — moat tributário, quote-gated
# Ambos os planos concedem o MESMO nível de acesso às Decision Tools
# (GP5_ENTERPRISE); a Tabela do Gemini, "GP5 Enterprise" como único plano a
# US$ 5.000/mo, ficava 10x acima do anchor da prateleira.
PLANS = {
    "pro": {
        "label": "GP5 Pro",
        "name": "Aether Grid GP5 Pro - Chave MCP",
        "description": "Acesso ao Motor GP5 (Arbitragem Fiscal e Risco de Fretamento) - GP5 Pro",
        "monthly_cents": 49900,     # US$ 499/mo
        "yearly_cents": 499000,     # US$ 4.990/ano (2 meses grátis)
    },
    "enterprise": {
        "label": "GP5 Enterprise",
        "name": "Aether Grid GP5 - Chave de Acesso B2B",
        "description": "Acesso ao Motor GP5 (Arbitragem Fiscal e Risco de Fretamento) - GP5 Enterprise",
        "monthly_cents": 500000,    # US$ 5.000/mo
        "yearly_cents": 5000000,    # US$ 50.000/ano
    },
}
VALID_INTERVALS = {"month", "year"}
GP5_ENTERPRISE_PLAN = "GP5_ENTERPRISE"


def _require_stripe() -> None:
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe API Key não configurada no servidor.")


def _checkout_session(email: str, plan: str, interval: str) -> RedirectResponse:
    plan_key = plan.lower()
    if plan_key not in PLANS:
        raise HTTPException(status_code=400, detail=f"Plano inválido. Escolha entre: {', '.join(PLANS)}")
    if interval not in VALID_INTERVALS:
        raise HTTPException(status_code=400, detail="Intervalo inválido. Escolha month ou year.")
    cfg = PLANS[plan_key]
    unit_amount = cfg["monthly_cents"] if interval == "month" else cfg["yearly_cents"]
    _require_stripe()
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": cfg["name"],
                        "description": cfg["description"],
                    },
                    "unit_amount": unit_amount,
                    "recurring": {"interval": interval},
                },
                "quantity": 1,
            }],
            mode="subscription",
            customer_email=email,
            success_url=f"{PUBLIC_BASE_URL}/m2m-keys/fulfillment?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{PUBLIC_BASE_URL}/m2m-keys",
            metadata={
                "product": "gp5_monthly_m2m",
                "plan": plan_key,
            },
        )
        return RedirectResponse(url=session.url, status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Falha ao criar checkout Stripe: {e}")
        raise HTTPException(status_code=500, detail=f"Falha ao criar checkout: {e}")


@router.get("/checkout/gp5-monthly")
def checkout_gp5_monthly(
    email: str = Query(..., min_length=3),
    plan: str = "enterprise",
    interval: str = "month",
):
    """Inicia uma assinatura do GP5 (Pro US$ 499/mo ou Enterprise US$ 5k/mo).

    A chave M2M é emitida idempotentemente no webhook e/ou na página de
    fulfillment (mesma session_id -> mesma chave). Sem STRIPE_API_KEY no
    ambiente o checkout degrada em 503.
    """
    return _checkout_session(email, plan, interval)


@router.get("/checkout/gp5-pro")
def checkout_gp5_pro(
    email: str = Query(..., min_length=3),
    interval: str = "month",
):
    """Atalho do plano Pro (US$ 499/mo) para o checkout."""
    return _checkout_session(email, "pro", interval)


@router.get("/m2m-keys/fulfillment")
def m2m_keys_fulfillment(session_id: str = Query(...)):
    """
    Entrega real da chave paga após o pagamento.
    Idempotente: re-chamadas ou o webhook registram a MESMA chave por session_id.
    """
    _require_stripe()
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        return HTMLResponse(f"<p>Sessão inválida: {e}</p>", status_code=400)

    is_paid = session.get("payment_status") == "paid" or session.get("status") == "complete"
    if not is_paid:
        return HTMLResponse(
            "<p>Pagamento ainda não confirmado. Tente novamente em instantes.</p>"
        )

    email = session.get("customer_email") or (session.get("customer_details") or {}).get("email") or "cliente"
    meta = session.get("metadata") or {}
    # Nível do plano vindo do checkout (pro | enterprise). Padrão enterprise
    # para sessões legadas sem metadata (todas as chaves pagas eram Enterprise).
    paid_level = meta.get("plan", "enterprise")
    token = register_paid_m2m_key(
        "Stripe Customer", email, "Stripe", external_id=session_id, level=paid_level
    )

    html = f"""
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
    <body style="background:#0a0e14; color:#e6edf3; font-family:sans-serif; padding: 40px; text-align:center;">
        <h1 style="color:#00d992">Pagamento Aprovado!</h1>
        <p>Guarde sua chave de acesso M2M API (Bearer Token) — <b>não a exiba publicamente.</b></p>
        <h2 style="background:#161b22; padding:20px; border-radius:8px; border:1px solid #30363d; display:inline-block; user-select:all;">{token}</h2>
        <p>Utilize esta chave no header <code>Authorization: Bearer {token}</code> para autenticar agentes MCP e integrações REST.</p>
        <p>Chaves pagas (GP5 Pro / Enterprise) são permanentes e vinculadas à sua assinatura ativa.</p>
        <br>
        <a href="/docs" style="color:#58a6ff;">Ir para a Documentação da API</a>
    </body>
    </html>
    """
    return HTMLResponse(html)


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    """
    Webhook que confirma o pagamento e ativa a chave M2M no cofre JSON
    (mesmo cofre lido por authenticate_client). Idempotente por session_id.
    """
    payload = await request.body()
    if not stripe.api_key or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Stripe Webhook não configurado.")
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logging.error(f"Stripe Webhook signature failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        if session.get("metadata", {}).get("product") == "gp5_monthly_m2m":
            email = session.get("customer_email") or (session.get("customer_details") or {}).get("email") or "cliente"
            paid_level = (session.get("metadata") or {}).get("plan", "enterprise")
            token = register_paid_m2m_key(
                "Stripe Customer", email, "Stripe", external_id=session["id"], level=paid_level
            )
            logging.info(f"Pagamento aprovado! Chave GP5 {paid_level} ativada para {email}: {token[:24]}...")

    return {"status": "success"}