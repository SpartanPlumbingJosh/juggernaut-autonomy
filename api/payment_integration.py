import os
import stripe
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.database import query_db

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

async def create_payment_intent(amount: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Stripe payment intent."""
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            metadata=metadata,
            payment_method_types=['card'],
            receipt_email=metadata.get("customer_email", "")
        )
        return {
            "success": True,
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id
        }
    except stripe.error.StripeError as e:
        return {"success": False, "error": str(e)}

async def handle_stripe_webhook(payload: str, sig_header: str) -> Dict[str, Any]:
    """Handle Stripe webhook events."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except ValueError as e:
        return {"success": False, "error": "Invalid payload"}
    except stripe.error.SignatureVerificationError as e:
        return {"success": False, "error": "Invalid signature"}

    # Handle payment success
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        await record_transaction(
            payment_intent['id'],
            payment_intent['amount'],
            payment_intent['currency'],
            payment_intent['metadata'],
            "stripe"
        )
        return {"success": True, "message": "Payment recorded"}

    return {"success": True, "message": "Event not handled"}

async def record_transaction(
    transaction_id: str,
    amount_cents: int,
    currency: str,
    metadata: Dict[str, Any],
    source: str
) -> Dict[str, Any]:
    """Record a transaction in the revenue_tracking database."""
    try:
        metadata_json = json.dumps(metadata)
        await query_db(f"""
            INSERT INTO revenue_events (
                id, transaction_id, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                '{transaction_id}',
                {amount_cents},
                '{currency}',
                '{source}',
                '{metadata_json}'::jsonb,
                NOW(),
                NOW()
            )
        """)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
