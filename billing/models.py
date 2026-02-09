from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIAL = "trial"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"

class PaymentMethodType(str, Enum):
    CARD = "card"
    PAYPAL = "paypal"
    BANK_ACCOUNT = "bank_account"

class SubscriptionPlan:
    def __init__(self, 
                 id: str,
                 name: str,
                 description: str,
                 price_cents: int,
                 currency: str,
                 billing_interval: str,
                 trial_period_days: Optional[int] = None):
        self.id = id
        self.name = name
        self.description = description
        self.price_cents = price_cents
        self.currency = currency
        self.billing_interval = billing_interval
        self.trial_period_days = trial_period_days

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
        self.id = id
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
                 amount_due_cents: int,
                 currency: str,
                 status: str,
                 created: datetime,
                 period_start: datetime,
                 period_end: datetime,
                 paid: bool = False):
        self.id = id
        self.customer_id = customer_id
        self.amount_due_cents = amount_due_cents
        self.currency = currency
        self.status = status
        self.created = created
        self.period_start = period_start
        self.period_end = period_end
        self.paid = paid
