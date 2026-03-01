from __future__ import annotations
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


class SubscriptionStatus(Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    ENDED = "ended"


class InvoiceStatus(Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class PaymentEventType(Enum):
    CHARGE_SUCCEEDED = "charge_succeeded"
    CHARGE_FAILED = "charge_failed"
    SUBSCRIPTION_CREATED = "subscription_created"
    SUBSCRIPTION_UPDATED = "subscription_updated"


@dataclass
class Subscription:
    id: str
    customer_id: str
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    items: List[Dict[str, Any]]
    metadata: Dict[str, str]
    created_at: datetime
    updated_at: datetime = datetime.now()

    def days_remaining(self) -> int:
        return (self.current_period_end - datetime.now()).days

    def is_active(self) -> bool:
        return self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL)


@dataclass
class InvoiceLineItem:
    amount: float
    currency: str
    description: str
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


@dataclass
class Invoice:
    id: str
    customer_id: str
    amount_due: float
    amount_paid: float
    tax: float
    tax_rate: float
    status: InvoiceStatus
    due_date: datetime
    line_items: List[InvoiceLineItem]
    hosted_invoice_url: Optional[str] = None
    pdf_url: Optional[str] = None
