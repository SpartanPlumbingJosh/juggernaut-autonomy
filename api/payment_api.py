"""
Payment API - Handle Stripe, PayPal payments and subscriptions.

Endpoints:
- POST /payment/create - Create payment intent
- POST /payment/confirm - Confirm payment
- POST /payment/subscribe - Create subscription
- POST /payment/webhook - Payment webhook handler
"""

import os
import json
import stripe
import paypalrestsdk
from datetime import datetime
from typing import Any, Dict, Optional

from core.database import query_db

# Initialize payment providers
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

def _make_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(body)
    }

def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create error response."""
    return _make_response(status_code, {"error": message})

async def handle_create_payment(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create payment intent."""
    try:
        amount = int(float(body.get("amount", 0)) * 100)  # Convert to cents
        currency = body.get("currency", "usd")
        payment_method = body.get("payment_method", "stripe")
        metadata = body.get("metadata", {})
        
        if payment_method == "stripe":
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata,
                payment_method_types=["card"]
            )
            return _make_response(200, {
                "client_secret": intent.client_secret,
                "payment_id": intent.id,
                "payment_method": "stripe"
            })
            
        elif payment_method == "paypal":
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount/100:.2f}",
                        "currency": currency
                    }
                }],
                "redirect_urls": {
                    "return_url": os.getenv("PAYPAL_RETURN_URL"),
                    "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                }
            })
            
            if payment.create():
                return _make_response(200, {
                    "approval_url": payment.links[1].href,
                    "payment_id": payment.id,
                    "payment_method": "paypal"
                })
            else:
                return _error_response(400, payment.error)
                
        return _error_response(400, "Invalid payment method")
        
    except Exception as e:
        return _error_response(500, f"Payment creation failed: {str(e)}")

async def handle_confirm_payment(body: Dict[str, Any]) -> Dict[str, Any]:
    """Confirm payment."""
    try:
        payment_id = body.get("payment_id")
        payment_method = body.get("payment_method")
        
        if payment_method == "stripe":
            intent = stripe.PaymentIntent.confirm(payment_id)
            if intent.status == "succeeded":
                return _make_response(200, {"status": "success"})
            return _error_response(400, "Payment not succeeded")
            
        elif payment_method == "paypal":
            payment = paypalrestsdk.Payment.find(payment_id)
            if payment.execute({"payer_id": body.get("payer_id")}):
                return _make_response(200, {"status": "success"})
            return _error_response(400, payment.error)
            
        return _error_response(400, "Invalid payment method")
        
    except Exception as e:
        return _error_response(500, f"Payment confirmation failed: {str(e)}")

async def handle_create_subscription(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create subscription."""
    try:
        plan_id = body.get("plan_id")
        customer_id = body.get("customer_id")
        payment_method = body.get("payment_method")
        
        if payment_method == "stripe":
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"plan": plan_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return _make_response(200, {
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret,
                "status": subscription.status
            })
            
        elif payment_method == "paypal":
            agreement = paypalrestsdk.BillingAgreement({
                "name": "Subscription Agreement",
                "description": "Recurring subscription",
                "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z",
                "plan": {"id": plan_id},
                "payer": {"payment_method": "paypal"}
            })
            
            if agreement.create():
                return _make_response(200, {
                    "approval_url": agreement.links[0].href,
                    "agreement_id": agreement.id,
                    "status": "pending"
                })
            return _error_response(400, agreement.error)
            
        return _error_response(400, "Invalid payment method")
        
    except Exception as e:
        return _error_response(500, f"Subscription creation failed: {str(e)}")

async def handle_payment_webhook(body: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
    """Handle payment webhooks."""
    try:
        event = None
        payload = body.get("payload", {})
        
        if headers.get("x-stripe-signature"):
            # Verify Stripe webhook
            event = stripe.Webhook.construct_event(
                payload,
                headers["x-stripe-signature"],
                os.getenv("STRIPE_WEBHOOK_SECRET")
            )
            
        elif headers.get("paypal-transmission-id"):
            # Verify PayPal webhook
            if not paypalrestsdk.WebhookEvent.verify(
                headers["paypal-transmission-id"],
                headers["paypal-transmission-sig"],
                headers["paypal-transmission-time"],
                os.getenv("PAYPAL_WEBHOOK_ID"),
                payload
            ):
                return _error_response(400, "Invalid PayPal webhook")
            event = paypalrestsdk.WebhookEvent.find(headers["paypal-transmission-id"])
            
        if not event:
            return _error_response(400, "Invalid webhook source")
            
        # Handle events
        if event.type == "payment_intent.succeeded":
            # Record successful payment
            await query_db(f"""
                INSERT INTO payments (
                    id, amount_cents, currency, status,
                    payment_method, metadata, created_at
                ) VALUES (
                    '{event.data.object.id}',
                    {event.data.object.amount},
                    '{event.data.object.currency}',
                    'succeeded',
                    'stripe',
                    '{json.dumps(event.data.object.metadata)}'::jsonb,
                    NOW()
                )
            """)
            
        elif event.type == "PAYMENT.SALE.COMPLETED":
            # Record PayPal payment
            await query_db(f"""
                INSERT INTO payments (
                    id, amount_cents, currency, status,
                    payment_method, metadata, created_at
                ) VALUES (
                    '{payload.id}',
                    {int(float(payload.amount.total) * 100)},
                    '{payload.amount.currency}',
                    'succeeded',
                    'paypal',
                    '{json.dumps(payload)}'::jsonb,
                    NOW()
                )
            """)
            
        return _make_response(200, {"status": "success"})
        
    except Exception as e:
        return _error_response(500, f"Webhook processing failed: {str(e)}")

def route_payment_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route payment API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # POST /payment/create
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "create" and method == "POST":
        return handle_create_payment(json.loads(body or "{}"))
    
    # POST /payment/confirm
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "confirm" and method == "POST":
        return handle_confirm_payment(json.loads(body or "{}"))
    
    # POST /payment/subscribe
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "subscribe" and method == "POST":
        return handle_create_subscription(json.loads(body or "{}"))
    
    # POST /payment/webhook
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "webhook" and method == "POST":
        return handle_payment_webhook(json.loads(body or "{}"), query_params)
    
    return _error_response(404, "Not found")

__all__ = ["route_payment_request"]
