"""
Payment Processor - Handles Stripe integration and payment processing.
Includes webhook handlers for payment events and subscription management.
"""

import stripe
from datetime import datetime
from typing import Dict, Any, Optional

from core.db import execute_sql
from config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class PaymentProcessor:
    def __init__(self):
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    async def create_payment_intent(
        self,
        amount_cents: int,
        currency: str = "usd",
        metadata: Optional[Dict[str, Any]] = None,
        customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a Stripe PaymentIntent for one-time payments."""
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency.lower(),
            metadata=metadata or {},
            customer=customer_id,
            automatic_payment_methods={"enabled": True}
        )
        return {"client_secret": intent.client_secret}

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a Stripe subscription."""
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            metadata=metadata or {},
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"]
        )
        return {
            "subscription_id": subscription.id,
            "client_secret": subscription.latest_invoice.payment_intent.client_secret
        }

    async def record_transaction(
        self,
        stripe_event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record Stripe transaction in revenue_events table."""
        event_type = stripe_event["type"]
        event_data = stripe_event["data"]["object"]

        if event_type == "payment_intent.succeeded":
            amount = event_data["amount"]
            currency = event_data["currency"]
            customer_id = event_data.get("customer")
            metadata = event_data.get("metadata", {})
            experiment_id = metadata.get("experiment_id")

            await execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, experiment_id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    {f"'{experiment_id}'" if experiment_id else "NULL"},
                    'revenue',
                    {amount},
                    '{currency}',
                    'stripe',
                    '{json.dumps(metadata)}',
                    NOW(),
                    NOW()
                )
                """
            )
            return {"success": True}

        return {"success": False, "error": "Unhandled event type"}

    async def handle_webhook(
        self,
        payload: bytes,
        sig_header: str
    ) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
        except ValueError as e:
            return {"success": False, "error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            return {"success": False, "error": "Invalid signature"}

        # Route the event
        handler = getattr(self, f"handle_{event.type}", None)
        if handler:
            return await handler(event)
        return {"success": False, "error": "Unhandled event type"}
