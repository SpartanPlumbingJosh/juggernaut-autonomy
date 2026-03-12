import os
import stripe
import paddle
from datetime import datetime, timezone
from typing import Dict, Optional, List
from enum import Enum

# Initialize payment processors
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paddle.api_key = os.getenv("PADDLE_SECRET_KEY")

class PaymentProvider(Enum):
    STRIPE = "stripe"
    PADDLE = "paddle"

class SubscriptionTier(Enum):
    STARTER = "starter"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"

class PaymentProcessor:
    def __init__(self):
        self.provider = PaymentProvider.STRIPE if os.getenv("PAYMENT_PROVIDER") == "stripe" else PaymentProvider.PADDLE

    async def create_customer(self, email: str, name: str) -> Dict[str, Any]:
        """Create a new customer in the payment provider."""
        if self.provider == PaymentProvider.STRIPE:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"created_at": datetime.now(timezone.utc).isoformat()}
            )
            return customer
        else:
            customer = paddle.Customer.create(
                email=email,
                name=name,
                metadata={"created_at": datetime.now(timezone.utc).isoformat()}
            )
            return customer

    async def create_subscription(self, customer_id: str, tier: SubscriptionTier) -> Dict[str, Any]:
        """Create a new subscription for a customer."""
        if self.provider == PaymentProvider.STRIPE:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": self._get_stripe_price_id(tier)}],
                expand=["latest_invoice.payment_intent"]
            )
            return subscription
        else:
            subscription = paddle.Subscription.create(
                customer_id=customer_id,
                plan_id=self._get_paddle_plan_id(tier)
            )
            return subscription

    async def record_usage(self, customer_id: str, quantity: int) -> Dict[str, Any]:
        """Record usage for a metered subscription."""
        if self.provider == PaymentProvider.STRIPE:
            return stripe.SubscriptionItem.create_usage_record(
                subscription_item=self._get_subscription_item_id(customer_id),
                quantity=quantity,
                timestamp=int(datetime.now(timezone.utc).timestamp())
            )
        else:
            return paddle.Usage.create(
                customer_id=customer_id,
                quantity=quantity,
                timestamp=int(datetime.now(timezone.utc).timestamp())
            )

    async def create_invoice(self, customer_id: str) -> Dict[str, Any]:
        """Create an invoice for a customer."""
        if self.provider == PaymentProvider.STRIPE:
            return stripe.Invoice.create(customer=customer_id)
        else:
            return paddle.Invoice.create(customer_id=customer_id)

    async def handle_webhook(self, payload: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        """Handle payment provider webhooks."""
        if self.provider == PaymentProvider.STRIPE:
            event = stripe.Webhook.construct_event(
                payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET")
            )
            return self._process_stripe_event(event)
        else:
            event = paddle.Webhook.construct_event(
                payload, signature, os.getenv("PADDLE_WEBHOOK_SECRET")
            )
            return self._process_paddle_event(event)

    def _process_stripe_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        event_type = event["type"]
        data = event["data"]["object"]

        if event_type == "payment_intent.succeeded":
            return self._record_payment(data)
        elif event_type == "invoice.payment_succeeded":
            return self._record_invoice(data)
        elif event_type == "customer.subscription.updated":
            return self._update_subscription(data)
        else:
            return {"status": "unhandled_event"}

    def _process_paddle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process Paddle webhook events."""
        event_type = event["event_type"]
        data = event["data"]

        if event_type == "payment_succeeded":
            return self._record_payment(data)
        elif event_type == "invoice_paid":
            return self._record_invoice(data)
        elif event_type == "subscription_updated":
            return self._update_subscription(data)
        else:
            return {"status": "unhandled_event"}

    def _record_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record a payment in the database."""
        # Implementation depends on your database schema
        pass

    def _record_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record an invoice in the database."""
        # Implementation depends on your database schema
        pass

    def _update_subscription(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update subscription status in the database."""
        # Implementation depends on your database schema
        pass

    def _get_stripe_price_id(self, tier: SubscriptionTier) -> str:
        """Get Stripe price ID for a subscription tier."""
        return {
            SubscriptionTier.STARTER: os.getenv("STRIPE_STARTER_PRICE_ID"),
            SubscriptionTier.GROWTH: os.getenv("STRIPE_GROWTH_PRICE_ID"),
            SubscriptionTier.ENTERPRISE: os.getenv("STRIPE_ENTERPRISE_PRICE_ID")
        }[tier]

    def _get_paddle_plan_id(self, tier: SubscriptionTier) -> str:
        """Get Paddle plan ID for a subscription tier."""
        return {
            SubscriptionTier.STARTER: os.getenv("PADDLE_STARTER_PLAN_ID"),
            SubscriptionTier.GROWTH: os.getenv("PADDLE_GROWTH_PLAN_ID"),
            SubscriptionTier.ENTERPRISE: os.getenv("PADDLE_ENTERPRISE_PLAN_ID")
        }[tier]

    def _get_subscription_item_id(self, customer_id: str) -> str:
        """Get subscription item ID for a customer."""
        # Implementation depends on your database schema
        pass
