import os
import stripe
import logging
from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import RedirectResponse
from src.engine.init_prod_db import get_connection
import secrets

router = APIRouter(tags=["Monetization"])

stripe.api_key = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Preço Fixo (Pode ser substituído por um Price ID real do Stripe)
GP5_MONTHLY_PRICE_USD = 500000  # $5,000.00 in cents

@router.get("/checkout/gp5-monthly")
def checkout_gp5_monthly(email: str):
    """
    Inicia o fluxo de pagamento para a chave M2M do Motor GP5.
    Redireciona o cliente para o Checkout do Stripe.
    """
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe API Key não configurada.")
        
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "Aether Grid GP5 - Chave de Acesso B2B Mensal",
                        "description": "Acesso ilimitado ao Motor GP5 (Arbitragem Fiscal e Risco de Fretamento)",
                    },
                    "unit_amount": GP5_MONTHLY_PRICE_USD,
                },
                "quantity": 1,
            }],
            mode="payment",
            customer_email=email,
            success_url="https://aetherx.aether-grid.io/docs",
            cancel_url="https://aetherx.aether-grid.io/",
            metadata={"product": "gp5_monthly_m2m"}
        )
        return RedirectResponse(url=session.url, status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    """
    Webhook que recebe a confirmação de pagamento do Stripe,
    gera a chave M2M e cadastra no DuckDB de forma persistente.
    """
    payload = await request.body()
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
            email = session.get("customer_email") or session.get("customer_details", {}).get("email")
            
            # Gera a Chave M2M Permanente (m2m_...)
            key_token = "m2m_" + secrets.token_hex(16)
            
            # Salva no cofre DuckDB persistente!
            try:
                conn = get_connection()
                conn.execute(
                    "INSERT INTO m2m_keys (client_id, owner_name, plan, is_active) VALUES (?, ?, ?, ?)",
                    [key_token, f"Stripe Customer: {email}", "GP5_ENTERPRISE", True]
                )
                conn.commit()
                logging.info(f"Pagamento Aprovado! Chave M2M gerada para {email}: {key_token}")
                
                # Injeta métrica na Control Tower
                from src.api.metrics import track_paid_api_call
                track_paid_api_call("STRIPE_DIRECT", email)
            except Exception as db_err:
                logging.error(f"Erro ao salvar chave paga no DB: {db_err}")

    return {"status": "success"}

