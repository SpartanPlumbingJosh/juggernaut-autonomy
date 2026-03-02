import os
import stripe
import paddle
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from enum import Enum

class PaymentProvider(Enum):
    STRIPE = "stripe"
    PADDLE = "paddle"

class PaymentProcessor:
    def __init__(self):
        self.stripe_api_key = os.getenv("STRIPE_API_KEY")
        self.paddle_vendor_id = os.getenv("PADDLE_VENDOR_ID")
        self.paddle_auth_code = os.getenv("PADDLE_AUTH_CODE")
        
        if self.stripe_api_key:
            stripe.api_key = self.stripe_api_key
        
    async def create_customer(
        self,
        email: str,
        name: str,
        payment_method: str,
        provider: PaymentProvider = PaymentProvider.STRIPE
    ) -> Dict:
        """Create a new customer in payment provider."""
        if provider == PaymentProvider.STRIPE:
            return stripe.Customer.create(
                email=email,
                name=name,
                payment_method=payment_method
            )
        elif provider == PaymentProvider.PADDLE:
            return paddle.Customer.create(
                email=email,
                name=name,
                payment_method=payment_method
            )
        raise ValueError(f"Unsupported payment provider: {provider}")

    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        trial_days: int = 0,
        provider: PaymentProvider = PaymentProvider.STRIPE
    ) -> Dict:
        """Create a new subscription."""
        if provider == PaymentProvider.STRIPE:
            return stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id}],
                trial_period_days=trial_days
            )
        elif provider == PaymentProvider.PADDLE:
            return paddle.Subscription.create(
                customer_id=customer_id,
                plan_id=plan_id,
                trial_days=trial_days
            )
        raise ValueError(f"Unsupported payment provider: {provider}")

    async def record_usage(
        self,
        subscription_item_id: str,
        quantity: int,
        timestamp: datetime,
        provider: PaymentProvider = PaymentProvider.STRIPE
    ) -> Dict:
        """Record usage for metered billing."""
        if provider == PaymentProvider.STRIPE:
            return stripe.SubscriptionItem.create_usage_record(
                subscription_item_id,
                quantity=quantity,
                timestamp=int(timestamp.timestamp())
            )
        elif provider == PaymentProvider.PADDLE:
            return paddle.Usage.create(
                subscription_item_id=subscription_item_id,
                quantity=quantity,
                timestamp=timestamp.isoformat()
            )
        raise ValueError(f"Unsupported payment provider: {provider}")

    async def handle_webhook(
        self,
        payload: bytes,
        signature: str,
        provider: PaymentProvider = PaymentProvider.STRIPE
    ) -> Dict:
        """Process payment provider webhook."""
        if provider == PaymentProvider.STRIPE:
            event = stripe.Webhook.construct_event(
                payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET")
            )
            return await self._process_stripe_event(event)
        elif provider == PaymentProvider.PADDLE:
            event = paddle.Webhook.verify(
                payload, signature, os.getenv("PADDLE_PUBLIC_KEY")
            )
            return await self._process_paddle_event(event)
        raise ValueError(f"Unsupported payment provider: {provider}")

    async def _process_stripe_event(self, event: Dict) -> Dict:
        """Process Stripe webhook event."""
        event_type = event["type"]
        data = event["data"]["object"]
        
        if event_type == "invoice.payment_succeeded":
            return await self._handle_successful_payment(data)
        elif event_type == "invoice.payment_failed":
            return await self._handle_failed_payment(data)
        elif event_type == "customer.subscription.deleted":
            return await self._handle_subscription_cancelled(data)
        return {"status": "unhandled_event"}

    async def _process_paddle_event(self, event: Dict) -> Dict:
        """Process Paddle webhook event."""
        event_type = event["alert_name"]
        
        if event_type == "payment_succeeded":
            return await self._handle_successful_payment(event)
        elif event_type == "payment_failed":
            return await self._handle_failed_payment(event)
        elif event_type == "subscription_cancelled":
            return await self._handle_subscription_cancelled(event)
        return {"status": "unhandled_event"}

    async def _handle_successful_payment(self, data: Dict) -> Dict:
        """Handle successful payment event."""
        # TODO: Implement actual handling
        return {"status": "success", "event": "payment_succeeded"}

    async def _handle_failed_payment(self, data: Dict) -> Dict:
        """Handle failed payment event."""
        # TODO: Implement actual handling
        return {"status": "success", "event": "payment_failed"}

    async def _handle_subscription_cancelled(self, data: Dict) -> Dict:
        """Handle subscription cancellation."""
        # TODO: Implement actual handling
        return {"status": "success", "event": "subscription_cancelled"}
