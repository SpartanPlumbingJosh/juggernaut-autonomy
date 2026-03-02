import stripe
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from core.database import query_db

class StripeBilling:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.webhook_secret = None

    async def create_customer(self, email: str, name: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer": customer}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

    async def create_subscription(self, customer_id: str, price_id: str, trial_days: int = 0) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                trial_period_days=trial_days,
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            return {"success": True, "subscription": subscription}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: str, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            # Handle specific event types
            if event['type'] == 'invoice.payment_succeeded':
                await self._handle_payment_success(event['data']['object'])
            elif event['type'] == 'invoice.payment_failed':
                await self._handle_payment_failure(event['data']['object'])
            elif event['type'] == 'customer.subscription.deleted':
                await self._handle_subscription_cancelled(event['data']['object'])
            
            return {"success": True}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

    async def _handle_payment_success(self, invoice: Dict[str, Any]) -> None:
        """Record successful payment."""
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                '{invoice['id']}', 'revenue', {invoice['amount_paid']}, 
                '{invoice['currency']}', 'stripe',
                '{json.dumps(invoice)}', NOW(), NOW()
            )
        """)

    async def _handle_payment_failure(self, invoice: Dict[str, Any]) -> None:
        """Handle failed payment and initiate dunning process."""
        # Update subscription status
        await query_db(f"""
            UPDATE subscriptions
            SET status = 'payment_failed',
                last_payment_attempt = NOW()
            WHERE stripe_subscription_id = '{invoice['subscription']}'
        """)
        
        # Send notification to customer
        # Implement retry logic based on Stripe's retry schedule

    async def _handle_subscription_cancelled(self, subscription: Dict[str, Any]) -> None:
        """Handle subscription cancellation."""
        await query_db(f"""
            UPDATE subscriptions
            SET status = 'cancelled',
                cancelled_at = NOW()
            WHERE stripe_subscription_id = '{subscription['id']}'
        """)
