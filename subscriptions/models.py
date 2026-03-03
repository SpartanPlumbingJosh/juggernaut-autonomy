from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"

class SubscriptionPlan:
    def __init__(self, 
                 id: str,
                 name: str,
                 description: str,
                 price_cents: int,
                 currency: str,
                 billing_interval: str,
                 trial_period_days: int = 0):
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
                 trial_end: Optional[datetime] = None):
        self.id = id
        self.customer_id = customer_id
        self.plan_id = plan_id
        self.status = status
        self.current_period_start = current_period_start
        self.current_period_end = current_period_end
        self.cancel_at_period_end = cancel_at_period_end
        self.trial_end = trial_end

    def is_active(self) -> bool:
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]

    def days_until_renewal(self) -> int:
        return (self.current_period_end - datetime.utcnow()).days

class PaymentMethod:
    def __init__(self,
                 id: str,
                 customer_id: str,
                 type: str,
                 last4: str,
                 exp_month: int,
                 exp_year: int,
                 brand: str):
        self.id = id
        self.customer_id = customer_id
        self.type = type
        self.last4 = last4
        self.exp_month = exp_month
        self.exp_year = exp_year
        self.brand = brand
