import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from billing.models import (
    SubscriptionPlan,
    Subscription,
    Invoice,
    PaymentMethod,
    SubscriptionStatus,
    BillingFrequency
)
from billing.providers import PaymentProvider

logger = logging.getLogger(__name__)

class BillingService:
    def __init__(self, payment_provider: PaymentProvider):
        self.payment_provider = payment_provider

    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        payment_method_id: str,
        trial_days: int = 0,
        metadata: Optional[Dict[str, str]] = None
    ) -> Subscription:
        """Create a new subscription"""
        plan = await self.get_plan(plan_id)
        if not plan:
            raise ValueError("Plan not found")

        subscription = await self.payment_provider.create_subscription(
            customer_id=customer_id,
            plan_id=plan_id,
            payment_method_id=payment_method_id,
            trial_days=trial_days,
            metadata=metadata
        )
        return subscription

    async def cancel_subscription(self, subscription_id: str) -> Subscription:
        """Cancel a subscription"""
        return await self.payment_provider.cancel_subscription(subscription_id)

    async def update_subscription(
        self,
        subscription_id: str,
        plan_id: Optional[str] = None,
        payment_method_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Subscription:
        """Update subscription details"""
        return await self.payment_provider.update_subscription(
            subscription_id=subscription_id,
            plan_id=plan_id,
            payment_method_id=payment_method_id,
            metadata=metadata
        )

    async def get_subscription(self, subscription_id: str) -> Subscription:
        """Get subscription details"""
        return await self.payment_provider.get_subscription(subscription_id)

    async def list_subscriptions(
        self,
        customer_id: Optional[str] = None,
        status: Optional[SubscriptionStatus] = None,
        limit: int = 100
    ) -> List[Subscription]:
        """List subscriptions"""
        return await self.payment_provider.list_subscriptions(
            customer_id=customer_id,
            status=status,
            limit=limit
        )

    async def create_invoice(
        self,
        customer_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> Invoice:
        """Create a one-time invoice"""
        return await self.payment_provider.create_invoice(
            customer_id=customer_id,
            amount_cents=amount_cents,
            currency=currency,
            description=description,
            metadata=metadata
        )

    async def get_invoice(self, invoice_id: str) -> Invoice:
        """Get invoice details"""
        return await self.payment_provider.get_invoice(invoice_id)

    async def list_invoices(
        self,
        customer_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Invoice]:
        """List invoices"""
        return await self.payment_provider.list_invoices(
            customer_id=customer_id,
            subscription_id=subscription_id,
            limit=limit
        )

    async def create_payment_method(
        self,
        customer_id: str,
        payment_method_token: str
    ) -> PaymentMethod:
        """Add a payment method"""
        return await self.payment_provider.create_payment_method(
            customer_id=customer_id,
            payment_method_token=payment_method_token
        )

    async def get_payment_method(self, payment_method_id: str) -> PaymentMethod:
        """Get payment method details"""
        return await self.payment_provider.get_payment_method(payment_method_id)

    async def list_payment_methods(self, customer_id: str) -> List[PaymentMethod]:
        """List customer's payment methods"""
        return await self.payment_provider.list_payment_methods(customer_id)

    async def create_plan(self, plan: SubscriptionPlan) -> SubscriptionPlan:
        """Create a new subscription plan"""
        return await self.payment_provider.create_plan(plan)

    async def get_plan(self, plan_id: str) -> SubscriptionPlan:
        """Get plan details"""
        return await self.payment_provider.get_plan(plan_id)

    async def list_plans(self) -> List[SubscriptionPlan]:
        """List available plans"""
        return await self.payment_provider.list_plans()

    async def record_usage(
        self,
        subscription_id: str,
        metric_name: str,
        quantity: int
    ) -> None:
        """Record usage for a subscription"""
        await self.payment_provider.record_usage(
            subscription_id=subscription_id,
            metric_name=metric_name,
            quantity=quantity
        )

    async def process_payment_webhook(self, payload: Dict) -> None:
        """Process payment provider webhook"""
        await self.payment_provider.process_webhook(payload)
