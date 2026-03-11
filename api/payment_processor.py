import os
import stripe
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.database import query_db

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

async def create_payment_intent(amount_cents: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Stripe payment intent."""
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency.lower(),
            metadata=metadata,
            automatic_payment_methods={
                'enabled': True,
            },
        )
        return {
            "success": True,
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

async def handle_stripe_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """Handle Stripe webhook events."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )
    except ValueError as e:
        return {"success": False, "error": "Invalid payload"}
    except stripe.error.SignatureVerificationError as e:
        return {"success": False, "error": "Invalid signature"}

    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        await record_revenue_event(
            amount_cents=payment_intent['amount'],
            currency=payment_intent['currency'],
            source="stripe",
            metadata={
                "payment_intent_id": payment_intent['id'],
                "customer_email": payment_intent.get('receipt_email'),
                "payment_method": payment_intent['payment_method_types'][0]
            }
        )
    elif event['type'] == 'charge.refunded':
        charge = event['data']['object']
        await record_revenue_event(
            amount_cents=-charge['amount_refunded'],
            currency=charge['currency'],
            source="stripe_refund",
            metadata={
                "charge_id": charge['id'],
                "payment_intent_id": charge['payment_intent'],
                "reason": charge.get('refund_reason')
            }
        )

    return {"success": True}

async def record_revenue_event(
    amount_cents: int,
    currency: str,
    source: str,
    metadata: Dict[str, Any],
    event_type: str = "revenue"
) -> Dict[str, Any]:
    """Record a revenue event to the database."""
    try:
        metadata_json = json.dumps(metadata)
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                '{event_type}',
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

__all__ = ["create_payment_intent", "handle_stripe_webhook"]
