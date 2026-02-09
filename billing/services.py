import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import stripe
from paypalrestsdk import Payment

from billing.models import (
    PaymentMethod,
    SubscriptionStatus,
    SubscriptionPlan,
    Subscription,
    InvoiceStatus,
    Invoice,
    PaymentIntentStatus,
    PaymentIntent,
    Receipt
)

logger = logging.getLogger(__name__)

class BillingService:
    def __init__(self, stripe_api_key: str, paypal_client_id: str, paypal_secret: str):
        stripe.api_key = stripe_api_key
        self.paypal_client_id = paypal_client_id
        self.paypal_secret = paypal_secret

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: PaymentMethod) -> Subscription:
        """Create a new subscription"""
        if payment_method == PaymentMethod.STRIPE:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"plan": plan_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return self._map_stripe_subscription(subscription)
        elif payment_method == PaymentMethod.PAYPAL:
            # PayPal subscription logic
            pass
        raise ValueError("Unsupported payment method")

    async def cancel_subscription(self, subscription_id: str, payment_method: PaymentMethod) -> Subscription:
        """Cancel a subscription"""
        if payment_method == PaymentMethod.STRIPE:
            subscription = stripe.Subscription.delete(subscription_id)
            return self._map_stripe_subscription(subscription)
        elif payment_method == PaymentMethod.PAYPAL:
            # PayPal cancellation logic
            pass
        raise ValueError("Unsupported payment method")

    async def create_payment_intent(self, amount_cents: int, currency: str, payment_method: PaymentMethod) -> PaymentIntent:
        """Create a payment intent"""
        if payment_method == PaymentMethod.STRIPE:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                payment_method_types=["card"]
            )
            return self._map_stripe_payment_intent(intent)
        elif payment_method == PaymentMethod.PAYPAL:
            payment = Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": str(amount_cents / 100),
                        "currency": currency
                    }
                }]
            })
            if payment.create():
                return self._map_paypal_payment(payment)
        raise ValueError("Unsupported payment method")

    async def handle_webhook(self, payload: Dict[str, Any], signature: str, payment_method: PaymentMethod) -> bool:
        """Handle payment webhook events"""
        if payment_method == PaymentMethod.STRIPE:
            event = stripe.Webhook.construct_event(
                payload, signature, stripe.api_key
            )
            return await self._handle_stripe_webhook(event)
        elif payment_method == PaymentMethod.PAYPAL:
            # PayPal webhook handling
            pass
        return False

    async def _handle_stripe_webhook(self, event: stripe.Event) -> bool:
        """Handle Stripe webhook events"""
        event_type = event['type']
        data = event['data']['object']

        if event_type == 'invoice.payment_succeeded':
            await self._handle_payment_success(data)
        elif event_type == 'invoice.payment_failed':
            await self._handle_payment_failure(data)
        elif event_type == 'customer.subscription.deleted':
            await self._handle_subscription_cancellation(data)
        elif event_type == 'charge.refunded':
            await self._handle_refund(data)
        return True

    def _map_stripe_subscription(self, subscription: stripe.Subscription) -> Subscription:
        """Map Stripe subscription to our model"""
        return Subscription(
            id=subscription.id,
            customer_id=subscription.customer,
            plan_id=subscription.plan.id,
            status=SubscriptionStatus(subscription.status),
            current_period_start=datetime.fromtimestamp(subscription.current_period_start),
            current_period_end=datetime.fromtimestamp(subscription.current_period_end),
            cancel_at_period_end=subscription.cancel_at_period_end,
            created_at=datetime.fromtimestamp(subscription.created),
            metadata=subscription.metadata
        )

    def _map_stripe_payment_intent(self, intent: stripe.PaymentIntent) -> PaymentIntent:
        """Map Stripe payment intent to our model"""
        return PaymentIntent(
            id=intent.id,
            customer_id=intent.customer,
            amount_cents=intent.amount,
            currency=intent.currency,
            status=PaymentIntentStatus(intent.status),
            payment_method=PaymentMethod.STRIPE,
            created_at=datetime.fromtimestamp(intent.created),
            metadata=intent.metadata
        )

    def _map_paypal_payment(self, payment: Payment) -> PaymentIntent:
        """Map PayPal payment to our model"""
        return PaymentIntent(
            id=payment.id,
            customer_id=payment.payer.payer_info.email,
            amount_cents=int(float(payment.transactions[0].amount.total) * 100),
            currency=payment.transactions[0].amount.currency,
            status=PaymentIntentStatus.SUCCEEDED,
            payment_method=PaymentMethod.PAYPAL,
            created_at=datetime.now(),
            metadata={}
        )
