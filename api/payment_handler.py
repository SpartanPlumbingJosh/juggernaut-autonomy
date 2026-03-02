import os
import stripe
import json
from datetime import datetime, timezone
from typing import Dict, Any

from core.database import query_db

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

async def handle_stripe_webhook(payload: str, sig_header: str) -> Dict[str, Any]:
    """Process Stripe webhook events."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except ValueError as e:
        return {"error": "Invalid payload", "status": 400}
    except stripe.error.SignatureVerificationError as e:
        return {"error": "Invalid signature", "status": 400}

    # Handle specific event types
    event_type = event['type']
    data = event['data']['object']
    
    if event_type == 'payment_intent.succeeded':
        await log_payment_event(data, 'payment_success')
        return {"status": "success", "event": event_type}
    elif event_type == 'payment_intent.payment_failed':
        await log_payment_event(data, 'payment_failed')
        return {"status": "success", "event": event_type}
    elif event_type == 'charge.refunded':
        await log_payment_event(data, 'refund_processed')
        return {"status": "success", "event": event_type}
    else:
        return {"status": "unhandled_event", "event": event_type}

async def log_payment_event(data: Dict[str, Any], event_type: str) -> None:
    """Securely log payment events to revenue_events table."""
    amount = data.get('amount', 0)
    currency = data.get('currency', 'usd')
    payment_id = data.get('id', '')
    metadata = data.get('metadata', {})
    
    await query_db(f"""
        INSERT INTO revenue_events (
            id, event_type, amount_cents, currency,
            source, metadata, recorded_at, created_at
        ) VALUES (
            gen_random_uuid(),
            '{event_type}',
            {amount},
            '{currency}',
            'stripe',
            '{json.dumps(metadata)}'::jsonb,
            NOW(),
            NOW()
        )
    """)

async def create_payment_intent(amount: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Stripe PaymentIntent."""
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            metadata=metadata,
            payment_method_types=['card'],
        )
        return {
            "client_secret": intent.client_secret,
            "id": intent.id,
            "status": intent.status
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}
