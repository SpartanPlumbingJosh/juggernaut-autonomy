"""
Payment API - Handle payment processing and transactions.

Endpoints:
- POST /payment/create-intent - Create payment intent
- POST /payment/confirm - Confirm payment
- POST /payment/webhook - Payment webhook handler
"""

import os
import stripe
import json
from datetime import datetime
from typing import Any, Dict, Optional

from core.database import query_db

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

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

async def create_payment_intent(amount: int, currency: str = 'usd', metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a payment intent with Stripe."""
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            automatic_payment_methods={
                'enabled': True,
            },
            metadata=metadata or {}
        )
        return _make_response(200, {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id
        })
    except stripe.error.StripeError as e:
        return _error_response(500, f"Payment error: {str(e)}")

async def confirm_payment(payment_intent_id: str) -> Dict[str, Any]:
    """Confirm a payment and record the transaction."""
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        if intent.status != 'succeeded':
            return _error_response(400, "Payment not succeeded")
            
        # Record transaction
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {intent.amount},
                '{intent.currency}',
                'stripe',
                '{json.dumps(intent.metadata)}'::jsonb,
                NOW(),
                NOW()
            )
        """)
        
        return _make_response(200, {"success": True})
    except Exception as e:
        return _error_response(500, f"Payment confirmation failed: {str(e)}")

async def handle_payment_webhook(payload: str, sig_header: str) -> Dict[str, Any]:
    """Handle Stripe webhook events."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
        
        # Handle specific event types
        if event['type'] == 'payment_intent.succeeded':
            intent = event['data']['object']
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source,
                    metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {intent['amount']},
                    '{intent['currency']}',
                    'stripe',
                    '{json.dumps(intent['metadata'])}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            
        return _make_response(200, {"success": True})
    except Exception as e:
        return _error_response(400, f"Webhook error: {str(e)}")

def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route payment API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # POST /payment/create-intent
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "create-intent" and method == "POST":
        try:
            data = json.loads(body or "{}")
            return create_payment_intent(
                amount=data.get("amount"),
                currency=data.get("currency", "usd"),
                metadata=data.get("metadata", {})
            )
        except Exception as e:
            return _error_response(400, f"Invalid request: {str(e)}")
    
    # POST /payment/confirm
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "confirm" and method == "POST":
        try:
            data = json.loads(body or "{}")
            return confirm_payment(data.get("payment_intent_id"))
        except Exception as e:
            return _error_response(400, f"Invalid request: {str(e)}")
    
    # POST /payment/webhook
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "webhook" and method == "POST":
        try:
            sig_header = query_params.get("stripe-signature", "")
            return handle_payment_webhook(body or "", sig_header)
        except Exception as e:
            return _error_response(400, f"Invalid request: {str(e)}")
    
    return _error_response(404, "Not found")

__all__ = ["route_request"]
