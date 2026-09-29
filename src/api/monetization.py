import os
import stripe
import logging
from fastapi import APIRouter, Request, Header, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse

from src.runtime.access import register_paid_m2m_key

router = APIRouter(tags=["Monetization"])

stripe.api_key = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://aetherx.aether-grid.io")

GP5_MONTHLY_PRICE_USD = 500000  # $5,000.00 em centavos (assinatura mensal)
GP5_ENTERPRISE_PLAN = "GP5_ENTERPRISE"


def _require_stripe() -> None:
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe API Key não configurada no servidor.")


@router.get("/checkout/gp5-monthly")
def checkout_gp5_monthly(email: str = Query(..., min_length=3)):
    """
    Inicia uma assinatura mensal do GP5 Enterprise no Checkout do Stripe.
    A chave M2M é emitida idempotentemente no webhook e/ou na página de
    fulfillment (mesma session_id -> mesma chave).
    """
    _require_stripe()
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "Aether Grid GP5 - Chave de Acesso B2B Mensal",
                        "description": "Acesso ao Motor GP5 (Arbitragem Fiscal e Risco de Fretamento) - GP5 Enterprise",
                    },
                    "unit_amount": GP5_MONTHLY_PRICE_USD,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            mode="subscription",
            customer_email=email,
            success_url=f"{PUBLIC_BASE_URL}/m2m-keys/fulfillment?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{PUBLIC_BASE_URL}/m2m-keys",
            metadata={
                "product": "gp5_monthly_m2m",
                "plan": GP5_ENTERPRISE_PLAN,
            },
        )
        return RedirectResponse(url=session.url, status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Falha ao criar checkout Stripe: {e}")
        raise HTTPException(status_code=500, detail=f"Falha ao criar checkout: {e}")


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
    token = register_paid_m2m_key(
        "Stripe Customer", email, "Stripe", external_id=session_id
    )

    html = f"""
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
    <body style="background:#0a0e14; color:#e6edf3; font-family:sans-serif; padding: 40px; text-align:center;">
        <h1 style="color:#00d992">Pagamento Aprovado!</h1>
        <p>Guarde sua chave de acesso M2M API (Bearer Token) — <b>não a exiba publicamente.</b></p>
        <h2 style="background:#161b22; padding:20px; border-radius:8px; border:1px solid #30363d; display:inline-block; user-select:all;">{token}</h2>
        <p>Utilize esta chave no header <code>Authorization: Bearer {token}</code> para autenticar agentes MCP e integrações REST.</p>
        <p>Chaves GP5 Enterprise são permanentes e vinculadas à sua assinatura ativa.</p>
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
            token = register_paid_m2m_key(
                "Stripe Customer", email, "Stripe", external_id=session["id"]
            )
            logging.info(f"Pagamento aprovado! Chave GP5 Enterprise ativada para {email}: {token[:24]}...")

    return {"status": "success"}