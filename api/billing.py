"""
Billing and subscription management system.
Integrates with Stripe for payment processing.
"""

import datetime
import json
import stripe
from typing import Dict, List, Optional

from core.config import settings
from core.database import query_db

stripe.api_key = settings.STRIPE_SECRET_KEY

async def create_customer(email: str, name: str, metadata: Optional[dict] = None) -> Dict:
    """Create a new billing customer in Stripe."""
    try:
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata=metadata or {}
        )
        return {"success": True, "customer": customer}
    except stripe.error.StripeError as e:
        return {"success": False, "error": str(e)}

async def create_subscription(customer_id: str, price_id: str) -> Dict:
    """Create a new subscription for a customer."""
    try:
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"]
        )
        return {"success": True, "subscription": subscription}
    except stripe.error.StripeError as e:
        return {"success": False, "error": str(e)}

async def record_payment_event(event_data: Dict) -> Dict:
    """Record completed payment in revenue_events."""
    amount = event_data["amount"] / 100  # Convert from cents
    metadata = json.dumps(event_data.get("metadata", {}))
    source = event_data.get("source", "stripe")
    
    sql = f"""
    INSERT INTO revenue_events (
        id, 
        event_type, 
        amount_cents, 
        currency,
        source,
        metadata,
        recorded_at,
        created_at
    ) VALUES (
        gen_random_uuid(),
        'revenue',
        {amount},
        '{event_data["currency"]}',
        '{source}',
        '{metadata}'::jsonb,
        NOW(),
        NOW()
    )
    RETURNING id
    """
    
    result = await query_db(sql)
    return {"success": True, "event_id": result["rows"][0]["id"]}

async def handle_webhook(payload: Dict) -> Dict:
    """Process Stripe webhook events."""
    event = payload.get("data", {}).get("object", {})
    
    if payload["type"] == "invoice.payment_succeeded":
        return await record_payment_event({
            "amount": event["amount_paid"],
            "currency": event["currency"],
            "customer": event["customer"],
            "metadata": event.get("metadata", {})
        })
    
    return {"success": False, "error": "Unhandled event type"}
