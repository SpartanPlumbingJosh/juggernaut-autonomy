import stripe
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.database import execute_sql

class StripeProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.currency = "usd"

    async def create_payment_intent(self, amount_cents: int, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=self.currency,
                metadata=metadata,
                automatic_payment_methods={"enabled": True},
            )
            return {"success": True, "client_secret": intent.client_secret}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """Handle Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError as e:
            return {"success": False, "error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            return {"success": False, "error": "Invalid signature"}

        # Handle the event
        if event["type"] == "payment_intent.succeeded":
            payment_intent = event["data"]["object"]
            await self._record_payment(payment_intent)
        elif event["type"] == "payment_intent.payment_failed":
            payment_intent = event["data"]["object"]
            await self._record_failed_payment(payment_intent)

        return {"success": True}

    async def _record_payment(self, payment_intent: Dict[str, Any]) -> None:
        """Record successful payment in database."""
        amount_cents = payment_intent["amount"]
        metadata = payment_intent.get("metadata", {})
        
        await execute_sql(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                '{self.currency}',
                'stripe',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
            """
        )

    async def _record_failed_payment(self, payment_intent: Dict[str, Any]) -> None:
        """Record failed payment attempt."""
        amount_cents = payment_intent["amount"]
        metadata = payment_intent.get("metadata", {})
        
        await execute_sql(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'payment_failed',
                {amount_cents},
                '{self.currency}',
                'stripe',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
            """
        )
