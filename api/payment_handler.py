"""
Payment processing integration with Stripe.

Handles:
- Payment intents creation
- Webhook events
- Idempotency checks
"""

import json
import stripe
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db

# Initialize Stripe
stripe.api_key = "sk_test_..."  # Should be from environment variable

def _make_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(body)
    }

async def create_payment_intent(amount: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Stripe payment intent."""
    try:
        # Check for existing payment with same idempotency key
        idempotency_key = metadata.get("idempotency_key")
        if idempotency_key:
            existing = await query_db(f"""
                SELECT id FROM revenue_events 
                WHERE metadata->>'idempotency_key' = '{idempotency_key}'
                LIMIT 1
            """)
            if existing.get("rows"):
                return _make_response(200, {"status": "already_processed"})

        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            metadata=metadata,
            payment_method_types=['card'],
            capture_method='automatic'
        )
        
        return _make_response(200, {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id
        })
    except stripe.error.StripeError as e:
        return _make_response(400, {"error": str(e)})

async def handle_stripe_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process Stripe webhook events."""
    try:
        event_type = event['type']
        data = event['data']['object']
        
        if event_type == 'payment_intent.succeeded':
            return await _handle_successful_payment(data)
        elif event_type == 'payment_intent.payment_failed':
            return await _handle_failed_payment(data)
        else:
            return _make_response(200, {"status": "unhandled_event"})
            
    except Exception as e:
        return _make_response(500, {"error": str(e)})

async def _handle_successful_payment(payment: Dict[str, Any]) -> Dict[str, Any]:
    """Record successful payment."""
    try:
        # Check for existing record
        existing = await query_db(f"""
            SELECT id FROM revenue_events 
            WHERE metadata->>'payment_intent_id' = '{payment['id']}'
            LIMIT 1
        """)
        if existing.get("rows"):
            return _make_response(200, {"status": "already_recorded"})

        # Record revenue event
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {payment['amount']},
                '{payment['currency']}',
                'stripe',
                '{json.dumps(payment['metadata'])}'::jsonb,
                NOW(),
                NOW()
            )
        """)
        
        return _make_response(200, {"status": "success"})
    except Exception as e:
        return _make_response(500, {"error": str(e)})

async def _handle_failed_payment(payment: Dict[str, Any]) -> Dict[str, Any]:
    """Handle failed payment attempts."""
    try:
        # Log failure for analysis
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'payment_failed',
                {payment['amount']},
                '{payment['currency']}',
                'stripe',
                '{json.dumps(payment['metadata'])}'::jsonb,
                NOW(),
                NOW()
            )
        """)
        
        return _make_response(200, {"status": "failure_recorded"})
    except Exception as e:
        return _make_response(500, {"error": str(e)})

__all__ = ["create_payment_intent", "handle_stripe_webhook"]
