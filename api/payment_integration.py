"""
Payment Integration - Handle Stripe/PayPal/crypto payments and webhooks.
"""

import os
import json
import stripe
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

async def create_payment_intent(amount_cents: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Stripe payment intent."""
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency.lower(),
            metadata=metadata,
            automatic_payment_methods={"enabled": True},
        )
        return {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
            "status": intent.status
        }
    except Exception as e:
        return {"error": str(e)}

async def handle_stripe_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """Handle Stripe webhook events."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except ValueError as e:
        return {"error": "Invalid payload"}
    except stripe.error.SignatureVerificationError as e:
        return {"error": "Invalid signature"}

    # Handle the event
    event_type = event['type']
    data = event['data']['object']
    
    if event_type == 'payment_intent.succeeded':
        await log_transaction(
            event_id=data['id'],
            amount_cents=data['amount'],
            currency=data['currency'],
            status='success',
            source='stripe',
            metadata=data.get('metadata', {})
        )
    elif event_type == 'payment_intent.payment_failed':
        await log_transaction(
            event_id=data['id'],
            amount_cents=data['amount'],
            currency=data['currency'],
            status='failed',
            source='stripe',
            metadata=data.get('metadata', {})
        )
    
    return {"success": True}

async def log_transaction(
    event_id: str,
    amount_cents: int,
    currency: str,
    status: str,
    source: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Log transaction to database."""
    try:
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, status, metadata, recorded_at
            ) VALUES (
                '{event_id}',
                'revenue',
                {amount_cents},
                '{currency}',
                '{source}',
                '{status}',
                '{json.dumps(metadata)}',
                NOW()
            )
        """)
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}

__all__ = ["create_payment_intent", "handle_stripe_webhook"]
