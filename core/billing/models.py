from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum

class InvoiceStatus(Enum):
    DRAFT = 'draft'
    OPEN = 'open'
    PAID = 'paid'
    VOID = 'void'
    UNCOLLECTIBLE = 'uncollectible'

class SubscriptionStatus(Enum):
    ACTIVE = 'active'
    PAST_DUE = 'past_due'
    CANCELED = 'canceled'
    UNPAID = 'unpaid'

class PaymentAttemptStatus(Enum):
    PENDING = 'pending'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    CANCELED = 'canceled'

class Invoice:
    def __init__(self,
                 invoice_id: str,
                 customer_id: str,
                 amount: float,
                 currency: str,
                 status: InvoiceStatus = InvoiceStatus.DRAFT,
                 due_date: Optional[datetime] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.invoice_id = invoice_id
        self.customer_id = customer_id
        self.amount = amount
        self.currency = currency
        self.status = status
        self.due_date = due_date or (datetime.utcnow() + timedelta(days=30))
        self.metadata = metadata or {}

class Subscription:
    def __init__(self,
                 subscription_id: str,
                 customer_id: str,
                 plan_id: str,
                 status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
                 current_period_end: Optional[datetime] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.subscription_id = subscription_id
        self.customer_id = customer_id
        self.plan_id = plan_id
        self.status = status
        self.current_period_end = current_period_end or (datetime.utcnow() + timedelta(days=30))
        self.metadata = metadata or {}

class PaymentAttempt:
    def __init__(self,
                 attempt_id: str,
                 payment_id: str,
                 amount: float,
                 currency: str,
                 status: PaymentAttemptStatus = PaymentAttemptStatus.PENDING,
                 retry_count: int = 0,
                 last_attempt: Optional[datetime] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.attempt_id = attempt_id
        self.payment_id = payment_id
        self.amount = amount
        self.currency = currency
        self.status = status
        self.retry_count = retry_count
        self.last_attempt = last_attempt or datetime.utcnow()
        self.metadata = metadata or {}
