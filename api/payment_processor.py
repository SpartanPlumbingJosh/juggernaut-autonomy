import stripe
import json
from datetime import datetime
from typing import Dict, Any, Optional
from core.database import query_db

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.stripe = stripe

    async def create_customer(self, email: str, name: str) -> Dict[str, Any]:
        """Create a new Stripe customer."""
        try:
            customer = self.stripe.Customer.create(
                email=email,
                name=name,
                metadata={"created_at": datetime.utcnow().isoformat()}
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_subscription(
        self, 
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a subscription for a customer."""
        try:
            subscription = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                metadata=metadata or {}
            )
            return {"success": True, "subscription_id": subscription.id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def record_payment_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Record a payment event in our revenue database."""
        event_type = event.get("type")
        if not event_type:
            return {"success": False, "error": "Missing event type"}

        amount = event.get("data", {}).get("object", {}).get("amount", 0)
        currency = event.get("data", {}).get("object", {}).get("currency", "usd")
        customer_id = event.get("data", {}).get("object", {}).get("customer", "")
        payment_id = event.get("data", {}).get("object", {}).get("id", "")

        try:
            await query_db(
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
                    '{json.dumps(event)}'::jsonb,
                    NOW(),
                    NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
