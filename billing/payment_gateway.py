import os
import stripe
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.database import execute_sql

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class PaymentGateway:
    """Handle payment processing and subscriptions."""
    
    def __init__(self):
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    async def create_customer(self, email: str, name: str) -> Dict[str, Any]:
        """Create a new customer in Stripe."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"created_at": datetime.now(timezone.utc).isoformat()}
            )
            return {"success": True, "customer_id": customer.id}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
    
    async def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
    
    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
        except ValueError as e:
            return {"success": False, "error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            return {"success": False, "error": "Invalid signature"}
        
        # Handle specific event types
        event_type = event["type"]
        data = event["data"]["object"]
        
        if event_type == "payment_intent.succeeded":
            await self._record_payment(data)
        elif event_type == "invoice.payment_succeeded":
            await self._record_subscription_payment(data)
        elif event_type == "invoice.payment_failed":
            await self._handle_payment_failure(data)
        
        return {"success": True}
    
    async def _record_payment(self, payment_intent: Dict[str, Any]) -> None:
        """Record a successful payment."""
        amount = payment_intent["amount"] / 100  # Convert from cents
        metadata = payment_intent.get("metadata", {})
        
        await execute_sql(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(amount * 100)},
                '{payment_intent["currency"]}',
                'stripe',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
            """
        )
    
    async def _record_subscription_payment(self, invoice: Dict[str, Any]) -> None:
        """Record a subscription payment."""
        amount = invoice["amount_paid"] / 100  # Convert from cents
        subscription_id = invoice["subscription"]
        
        await execute_sql(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(amount * 100)},
                '{invoice["currency"]}',
                'stripe_subscription',
                '{json.dumps({"subscription_id": subscription_id})}'::jsonb,
                NOW(),
                NOW()
            )
            """
        )
    
    async def _handle_payment_failure(self, invoice: Dict[str, Any]) -> None:
        """Handle failed payment attempts."""
        # Implement retry logic or notify customer
        pass
