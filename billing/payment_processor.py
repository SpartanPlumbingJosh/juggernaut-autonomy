import stripe
import paddle
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from enum import Enum

class PaymentProvider(Enum):
    STRIPE = "stripe"
    PADDLE = "paddle"

class SubscriptionStatus(Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"

class PaymentProcessor:
    def __init__(self, stripe_api_key: str, paddle_vendor_id: str, paddle_auth_code: str):
        stripe.api_key = stripe_api_key
        self.paddle_vendor_id = paddle_vendor_id
        self.paddle_auth_code = paddle_auth_code
        
    async def create_customer(self, email: str, name: str, payment_provider: PaymentProvider) -> Dict:
        """Create a customer in the payment provider"""
        if payment_provider == PaymentProvider.STRIPE:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"created_at": datetime.utcnow().isoformat()}
            )
            return customer
        elif payment_provider == PaymentProvider.PADDLE:
            customer = paddle.Customer.create(
                email=email,
                vendor_id=self.paddle_vendor_id,
                auth_code=self.paddle_auth_code
            )
            return customer
        raise ValueError("Invalid payment provider")

    async def create_subscription(self, customer_id: str, plan_id: str, payment_provider: PaymentProvider) -> Dict:
        """Create a new subscription"""
        if payment_provider == PaymentProvider.STRIPE:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return subscription
        elif payment_provider == PaymentProvider.PADDLE:
            subscription = paddle.Subscription.create(
                plan_id=plan_id,
                customer_id=customer_id,
                vendor_id=self.paddle_vendor_id,
                auth_code=self.paddle_auth_code
            )
            return subscription
        raise ValueError("Invalid payment provider")

    async def update_subscription(self, subscription_id: str, new_plan_id: str, payment_provider: PaymentProvider) -> Dict:
        """Update an existing subscription"""
        if payment_provider == PaymentProvider.STRIPE:
            subscription = stripe.Subscription.modify(
                subscription_id,
                items=[{"price": new_plan_id}],
                proration_behavior="create_prorations"
            )
            return subscription
        elif payment_provider == PaymentProvider.PADDLE:
            subscription = paddle.Subscription.update(
                subscription_id,
                new_plan_id=new_plan_id,
                vendor_id=self.paddle_vendor_id,
                auth_code=self.paddle_auth_code
            )
            return subscription
        raise ValueError("Invalid payment provider")

    async def cancel_subscription(self, subscription_id: str, payment_provider: PaymentProvider) -> Dict:
        """Cancel a subscription"""
        if payment_provider == PaymentProvider.STRIPE:
            subscription = stripe.Subscription.delete(subscription_id)
            return subscription
        elif payment_provider == PaymentProvider.PADDLE:
            subscription = paddle.Subscription.cancel(
                subscription_id,
                vendor_id=self.paddle_vendor_id,
                auth_code=self.paddle_auth_code
            )
            return subscription
        raise ValueError("Invalid payment provider")

    async def handle_webhook(self, payload: bytes, signature: str, payment_provider: PaymentProvider) -> Dict:
        """Handle payment provider webhook"""
        if payment_provider == PaymentProvider.STRIPE:
            event = stripe.Webhook.construct_event(
                payload, signature, stripe.webhook_secret
            )
            return self._process_stripe_event(event)
        elif payment_provider == PaymentProvider.PADDLE:
            event = paddle.Webhook.verify(
                payload, signature, self.paddle_auth_code
            )
            return self._process_paddle_event(event)
        raise ValueError("Invalid payment provider")

    def _process_stripe_event(self, event: Dict) -> Dict:
        """Process Stripe webhook event"""
        event_type = event['type']
        data = event['data']
        
        if event_type == 'invoice.payment_succeeded':
            return self._handle_payment_success(data['object'])
        elif event_type == 'invoice.payment_failed':
            return self._handle_payment_failure(data['object'])
        elif event_type == 'customer.subscription.updated':
            return self._handle_subscription_update(data['object'])
        elif event_type == 'customer.subscription.deleted':
            return self._handle_subscription_cancellation(data['object'])
        return {"status": "unhandled_event"}

    def _process_paddle_event(self, event: Dict) -> Dict:
        """Process Paddle webhook event"""
        event_type = event['alert_name']
        
        if event_type == 'subscription_payment_succeeded':
            return self._handle_payment_success(event)
        elif event_type == 'subscription_payment_failed':
            return self._handle_payment_failure(event)
        elif event_type == 'subscription_updated':
            return self._handle_subscription_update(event)
        elif event_type == 'subscription_cancelled':
            return self._handle_subscription_cancellation(event)
        return {"status": "unhandled_event"}

    def _handle_payment_success(self, payment_data: Dict) -> Dict:
        """Handle successful payment"""
        # Implement revenue recognition logic
        return {"status": "payment_success"}

    def _handle_payment_failure(self, payment_data: Dict) -> Dict:
        """Handle failed payment"""
        # Implement dunning management logic
        return {"status": "payment_failure"}

    def _handle_subscription_update(self, subscription_data: Dict) -> Dict:
        """Handle subscription changes"""
        return {"status": "subscription_updated"}

    def _handle_subscription_cancellation(self, subscription_data: Dict) -> Dict:
        """Handle subscription cancellation"""
        return {"status": "subscription_cancelled"}
