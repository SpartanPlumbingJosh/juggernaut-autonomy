"""
Billing Integration - Handle payments and subscriptions via Stripe/PayPal.
"""

import os
import stripe
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from core.database import query_db

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

async def create_payment_intent(amount_cents: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Stripe payment intent."""
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency.lower(),
            metadata=metadata,
            automatic_payment_methods={"enabled": True},
        )
        return {"client_secret": intent.client_secret}
    except Exception as e:
        return {"error": str(e)}

async def handle_stripe_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """Process Stripe webhook events."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except ValueError as e:
        return {"error": "Invalid payload"}
    except stripe.error.SignatureVerificationError as e:
        return {"error": "Invalid signature"}

    # Handle specific event types
    if event["type"] == "payment_intent.succeeded":
        payment = event["data"]["object"]
        await record_transaction(
            amount_cents=payment["amount"],
            currency=payment["currency"],
            source="stripe",
            metadata=payment["metadata"],
            recorded_at=datetime.fromtimestamp(payment["created"], timezone.utc)
        )
    elif event["type"] == "charge.refunded":
        charge = event["data"]["object"]
        await record_transaction(
            amount_cents=-charge["amount_refunded"],
            currency=charge["currency"],
            source="stripe",
            metadata=charge["metadata"],
            recorded_at=datetime.fromtimestamp(charge["created"], timezone.utc)
        )

    return {"success": True}

async def record_transaction(
    amount_cents: int,
    currency: str,
    source: str,
    metadata: Dict[str, Any],
    recorded_at: datetime
) -> None:
    """Record a transaction in the database."""
    metadata_json = json.dumps(metadata)
    await query_db(f"""
        INSERT INTO revenue_events (
            id, event_type, amount_cents, currency, source,
            metadata, recorded_at, created_at
        ) VALUES (
            gen_random_uuid(),
            'revenue',
            {amount_cents},
            '{currency}',
            '{source}',
            '{metadata_json}'::jsonb,
            '{recorded_at.isoformat()}',
            NOW()
        )
    """)

__all__ = ["create_payment_intent", "handle_stripe_webhook"]
