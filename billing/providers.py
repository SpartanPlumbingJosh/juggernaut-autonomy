from typing import Optional, List, Dict
from abc import ABC, abstractmethod

from billing.models import (
    SubscriptionPlan,
    Subscription,
    Invoice,
    PaymentMethod,
    SubscriptionStatus
)

class PaymentProvider(ABC):
    @abstractmethod
    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        payment_method_id: str,
        trial_days: int = 0,
        metadata: Optional[Dict[str, str]] = None
    ) -> Subscription:
        pass

    @abstractmethod
    async def cancel_subscription(self, subscription_id: str) -> Subscription:
        pass

    @abstractmethod
    async def update_subscription(
        self,
        subscription_id: str,
        plan_id: Optional[str] = None,
        payment_method_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Subscription:
        pass

    @abstractmethod
    async def get_subscription(self, subscription_id: str) -> Subscription:
        pass

    @abstractmethod
    async def list_subscriptions(
        self,
        customer_id: Optional[str] = None,
        status: Optional[SubscriptionStatus] = None,
        limit: int = 100
    ) -> List[Subscription]:
        pass

    @abstractmethod
    async def create_invoice(
        self,
        customer_id: str,
        amount_cents: int,
        currency: str,
        description: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> Invoice:
        pass

    @abstractmethod
    async def get_invoice(self, invoice_id: str) -> Invoice:
        pass

    @abstractmethod
    async def list_invoices(
        self,
        customer_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Invoice]:
        pass

    @abstractmethod
    async def create_payment_method(
        self,
        customer_id: str,
        payment_method_token: str
    ) -> PaymentMethod:
        pass

    @abstractmethod
    async def get_payment_method(self, payment_method_id: str) -> PaymentMethod:
        pass

    @abstractmethod
    async def list_payment_methods(self, customer_id: str) -> List[PaymentMethod]:
        pass

    @abstractmethod
    async def create_plan(self, plan: SubscriptionPlan) -> SubscriptionPlan:
        pass

    @abstractmethod
    async def get_plan(self, plan_id: str) -> SubscriptionPlan:
        pass

    @abstractmethod
    async def list_plans(self) -> List[SubscriptionPlan]:
        pass

    @abstractmethod
    async def record_usage(
        self,
        subscription_id: str,
        metric_name: str,
        quantity: int
    ) -> None:
        pass

    @abstractmethod
    async def process_webhook(self, payload: Dict) -> None:
        pass
