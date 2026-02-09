import os
import stripe
from typing import Dict, Any
from datetime import datetime

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

async def create_payment_intent(amount: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Stripe payment intent."""
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            metadata=metadata,
            payment_method_types=["card"],
        )
        return {
            "success": True,
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

async def handle_webhook_event(payload: str, sig_header: str) -> Dict[str, Any]:
    """Process Stripe webhook events."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
        
        if event["type"] == "payment_intent.succeeded":
            payment_intent = event["data"]["object"]
            return await _handle_payment_success(payment_intent)
            
        return {"success": True, "event": event["type"]}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def _handle_payment_success(payment_intent: Dict[str, Any]) -> Dict[str, Any]:
    """Handle successful payment."""
    from core.database import execute_sql
    
    metadata = payment_intent.get("metadata", {})
    amount = payment_intent.get("amount")
    currency = payment_intent.get("currency")
    
    try:
        await execute_sql(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount},
                '{currency}',
                'stripe',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
            """
        )
        return {"success": True, "payment_intent_id": payment_intent["id"]}
    except Exception as e:
        return {"success": False, "error": str(e)}
