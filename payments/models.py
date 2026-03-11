"""
Data models for payment processing system.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
import uuid

class PaymentMethodType(str, Enum):
    CARD = "card"
    PAYPAL = "paypal"
    BANK = "bank"

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    CANCELED = "canceled"
    TRIALING = "trialing"

class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"

class PaymentMethod:
    def __init__(self,
                 id: str,
                 customer_id: str,
                 type: PaymentMethodType,
                 details: Dict[str, Any],
                 is_default: bool = False,
                 created_at: Optional[datetime] = None):
        self.id = id or str(uuid.uuid4())
        self.customer_id = customer_id
        self.type = type
        self.details = details
        self.is_default = is_default
        self.created_at = created_at or datetime.utcnow()

class Subscription:
    def __init__(self,
                 id: str,
                 customer_id: str,
                 plan_id: str,
                 status: SubscriptionStatus,
                 current_period_start: datetime,
                 current_period_end: datetime,
                 cancel_at_period_end: bool = False,
                 metadata: Optional[Dict[str, Any]] = None):
        self.id = id or str(uuid.uuid4())
        self.customer_id = customer_id
        self.plan_id = plan_id
        self.status = status
        self.current_period_start = current_period_start
        self.current_period_end = current_period_end
        self.cancel_at_period_end = cancel_at_period_end
        self.metadata = metadata or {}

class Invoice:
    def __init__(self,
                 id: str,
                 customer_id: str,
                 subscription_id: Optional[str],
                 amount_due: int,
                 currency: str,
                 status: InvoiceStatus,
                 due_date: Optional[datetime] = None,
                 paid_at: Optional[datetime] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.id = id or str(uuid.uuid4())
        self.customer_id = customer_id
        self.subscription_id = subscription_id
        self.amount_due = amount_due
        self.currency = currency
        self.status = status
        self.due_date = due_date
        self.paid_at = paid_at
        self.metadata = metadata or {}
