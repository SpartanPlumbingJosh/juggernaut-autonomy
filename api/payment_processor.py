"""
Core payment processing and revenue tracking.
Handles Stripe integration and records revenue events.
"""

import json
import stripe
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from core.database import query_db

# Initialize Stripe
stripe.api_key = "sk_test_..."  # Should be from config

async def process_payment(
    amount_cents: int,
    currency: str,
    customer_email: str,
    product_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Process payment and record revenue event."""
    try:
        # Create Stripe payment intent
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency.lower(),
            receipt_email=customer_email,
            metadata={
                "product_id": product_id,
                **(metadata or {})
            }
        )

        # Record revenue event
        await record_revenue_event(
            amount_cents=amount_cents,
            currency=currency,
            source="stripe",
            event_type="revenue",
            metadata={
                "stripe_payment_intent": intent.id,
                "product_id": product_id,
                "customer_email": customer_email,
                **(metadata or {})
            }
        )

        return {
            "success": True,
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

async def record_revenue_event(
    amount_cents: int,
    currency: str,
    source: str,
    event_type: str,  # 'revenue' or 'cost'
    metadata: Optional[Dict[str, Any]] = None,
    attribution: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Record revenue or cost event in database."""
    try:
        result = await query_db(
            f"""
            INSERT INTO revenue_events (
                id,
                event_type,
                amount_cents,
                currency,
                source,
                metadata,
                attribution,
                recorded_at,
                created_at
            ) VALUES (
                gen_random_uuid(),
                '{event_type}',
                {amount_cents},
                '{currency}',
                '{source}',
                '{json.dumps(metadata or {})}'::jsonb,
                '{json.dumps(attribution or {})}'::jsonb,
                NOW(),
                NOW()
            )
            RETURNING id
            """
        )
        return {
            "success": True,
            "event_id": result.get("rows", [{}])[0].get("id")
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

async def fulfill_order(payment_intent_id: str) -> Dict[str, Any]:
    """Handle order fulfillment after successful payment."""
    try:
        # Verify payment was successful
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        if intent.status != "succeeded":
            return {"success": False, "error": "Payment not completed"}

        # Get product ID from metadata
        product_id = intent.metadata.get("product_id")
        if not product_id:
            return {"success": False, "error": "Missing product ID"}

        # TODO: Add product-specific fulfillment logic
        # This would call appropriate delivery/service methods
        
        return {
            "success": True,
            "product_id": product_id,
            "amount_received": intent.amount_received,
            "customer_email": intent.receipt_email
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
