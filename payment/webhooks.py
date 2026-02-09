import json
import hmac
import hashlib
from typing import Dict, Any
from fastapi import Request, HTTPException
from payment.processor import PaymentProcessor

processor = PaymentProcessor()

async def handle_stripe_webhook(request: Request) -> Dict[str, Any]:
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle specific event types
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        await processor.record_transaction({
            "amount": payment_intent["amount"] / 100,
            "currency": payment_intent["currency"],
            "source": "stripe",
            "metadata": payment_intent["metadata"]
        })
        await processor.fulfill_order(payment_intent["id"])
    
    return {"success": True}

async def handle_paypal_webhook(request: Request) -> Dict[str, Any]:
    """Handle PayPal webhook events."""
    payload = await request.json()
    headers = request.headers
    
    # Verify webhook signature
    webhook_id = os.getenv("PAYPAL_WEBHOOK_ID")
    transmission_id = headers.get("PAYPAL-TRANSMISSION-ID")
    timestamp = headers.get("PAYPAL-TRANSMISSION-TIME")
    cert_url = headers.get("PAYPAL-CERT-URL")
    signature = headers.get("PAYPAL-TRANSMISSION-SIG")
    
    message = f"{transmission_id}|{timestamp}|{webhook_id}|{hashlib.sha256(json.dumps(payload).encode()).hexdigest()}"
    
    if not paypalrestsdk.notifications.WebhookEvent.verify(
        message, cert_url, signature, paypalrestsdk.api.get_default().get_access_token()
    ):
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle specific event types
    if payload["event_type"] == "PAYMENT.CAPTURE.COMPLETED":
        resource = payload["resource"]
        await processor.record_transaction({
            "amount": float(resource["amount"]["value"]),
            "currency": resource["amount"]["currency_code"],
            "source": "paypal",
            "metadata": json.loads(resource["custom"] or "{}")
        })
        await processor.fulfill_order(resource["id"])
    
    return {"success": True}
