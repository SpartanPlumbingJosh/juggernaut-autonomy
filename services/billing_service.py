"""
Core billing service handling subscriptions, invoices and payment processing.
Integrated with Stripe for payment processing.
"""
import json
from datetime import datetime, timezone
from typing import Dict, Optional

import stripe
from core.database import query_db

class BillingService:
    def __init__(self, stripe_api_key: str):
        stripe.api_key = stripe_api_key
        self.webhook_secret = None  # Set via configure_webhooks
    
    async def create_customer(
        self, 
        email: str,
        user_id: str,
        name: Optional[str] = None
    ) -> Dict:
        """Create a Stripe customer and record in our system."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"user_id": user_id}
            )
            
            await self._record_customer(user_id, customer.id)
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        user_id: str,
    ) -> Dict:
        """Create recurring subscription with Stripe."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"],
                metadata={"user_id": user_id},
            )

            # Record revenue event
            await self._record_subscription_event(
                user_id=user_id,
                amount=subscription.latest_invoice.amount_due,
                subscription_id=subscription.id,
                invoice_id=subscription.latest_invoice.id
            )

            return {
                "success": True,
                "subscription_id": subscription.id,
                "payment_intent": subscription.latest_invoice.payment_intent,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _record_customer(self, user_id: str, customer_id: str):
        """Store Stripe customer ID in our database."""
        await query_db(
            f"""
            INSERT INTO billing_customers (user_id, stripe_id, created_at)
            VALUES ('{user_id}', '{customer_id}', NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET stripe_id = '{customer_id}'
            """
        )

    async def _record_subscription_event(
        self, 
        user_id: str,
        amount: int,
        subscription_id: str,
        invoice_id: str,
    ) -> None:
        """Record subscription revenue event in our tracking system."""
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id,
                event_type,
                amount_cents,
                currency,
                source,
                recorded_at,
                attribution
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount},
                'USD',
                'subscription',
                NOW(),
                jsonb_build_object(
                    'user_id', '{user_id}',
                    'subscription_id', '{subscription_id}',
                    'invoice_id', '{invoice_id}'
                )
            )
            """
        )

    def configure_webhooks(self, endpoint_secret: str):
        """Set Stripe webhook secret for validating events."""
        self.webhook_secret = endpoint_secret

    def parse_webhook(self, payload: bytes, sig_header: str) -> Dict:
        """Parse and validate Stripe webhook."""
        if not self.webhook_secret:
            raise ValueError("Webhook secret not configured")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return {"success": True, "event": event}
        except Exception as e:
            return {"success": False, "error": str(e)}
