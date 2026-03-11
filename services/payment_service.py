"""
Payment Service - Handles payment processing via Stripe/PayPal.
"""
import os
import stripe
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

# Configure Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY")

class PaymentIntentRequest(BaseModel):
    amount: int  # in cents
    currency: str = "usd"
    customer_id: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict] = None

@app.post("/payment-intents")
async def create_payment_intent(request: PaymentIntentRequest):
    try:
        intent = stripe.PaymentIntent.create(
            amount=request.amount,
            currency=request.currency,
            customer=request.customer_id,
            description=request.description,
            metadata=request.metadata or {}
        )
        return JSONResponse({
            "client_secret": intent.client_secret,
            "id": intent.id
        })
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/webhook/stripe")
async def handle_stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Handle different event types
    if event.type == "payment_intent.succeeded":
        # Process successful payment
        pass
    elif event.type == "invoice.payment_succeeded":
        # Process subscription payment
        pass

    return JSONResponse({"status": "success"})
