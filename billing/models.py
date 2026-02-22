"""
Data models for billing system.
"""

from datetime import datetime, timedelta
from typing import Optional
from enum import Enum, auto

class SubscriptionStatus(Enum):
    ACTIVE = auto()
    SUSPENDED = auto()
    CANCELLED = auto()
    TRIAL = auto()

class InvoiceStatus(Enum):
    DRAFT = auto()
    OPEN = auto()
    PAID = auto()
    VOID = auto()
    UNCOLLECTIBLE = auto()

class Subscription:
    def __init__(self, id: str, customer_id: str, plan_name: str,
                 plan_amount: float, plan_currency: str,
                 billing_cycle: str, next_billing_date: datetime,
                 payment_method_id: str, status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
                 failure_count: int = 0):
        self.id = id
        self.customer_id = customer_id
        self.plan_name = plan_name
        self.plan_amount = plan_amount
        self.plan_currency = plan_currency
        self.billing_cycle = billing_cycle
        self.next_billing_date = next_billing_date
        self.payment_method_id = payment_method_id
        self.status = status
        self.failure_count = failure_count

    def update_next_billing_date(self) -> None:
        """Update next billing date based on cycle"""
        if self.billing_cycle == 'monthly':
            self.next_billing_date += timedelta(days=30)
        elif self.billing_cycle == 'yearly':
            self.next_billing_date += timedelta(days=365)
        else:
            raise ValueError(f"Unknown billing cycle: {self.billing_cycle}")

    def increment_failure_count(self) -> None:
        """Increment payment failure counter"""
        self.failure_count += 1

    def suspend(self) -> None:
        """Suspend subscription due to payment failures"""
        self.status = SubscriptionStatus.SUSPENDED

class Invoice:
    def __init__(self, id: str, subscription_id: str, customer_id: str,
                 amount: float, currency: str, description: str,
                 status: InvoiceStatus = InvoiceStatus.DRAFT,
                 transaction_id: Optional[str] = None):
        self.id = id
        self.subscription_id = subscription_id
        self.customer_id = customer_id
        self.amount = amount
        self.currency = currency
        self.description = description
        self.status = status
        self.transaction_id = transaction_id
        self.total_amount = amount  # Could include taxes/fees in real implementation

    @classmethod
    def create(cls, subscription_id: str, customer_id: str, amount: float,
              currency: str, description: str) -> 'Invoice':
        """Factory method to create new invoice"""
        # In real implementation would generate unique ID
        return cls(
            id=f"inv_{datetime.now().timestamp()}",
            subscription_id=subscription_id,
            customer_id=customer_id,
            amount=amount,
            currency=currency,
            description=description
        )

    def mark_paid(self, transaction_id: str) -> None:
        """Mark invoice as paid"""
        self.status = InvoiceStatus.PAID
        self.transaction_id = transaction_id

    def mark_failed(self, error: Optional[str] = None) -> None:
        """Mark invoice as failed"""
        self.status = InvoiceStatus.UNCOLLECTIBLE
