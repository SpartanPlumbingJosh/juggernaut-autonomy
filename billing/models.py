from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum
from pydantic import BaseModel

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"

class SubscriptionPlan(BaseModel):
    id: str
    name: str
    description: Optional[str]
    price_cents: int
    currency: str
    billing_interval: str  # "month", "year"
    trial_period_days: Optional[int]

class Subscription(BaseModel):
    id: str
    customer_id: str
    plan_id: str
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    metadata: Dict[str, str]

class Invoice(BaseModel):
    id: str
    customer_id: str
    subscription_id: Optional[str]
    amount_due_cents: int
    amount_paid_cents: int
    currency: str
    status: str
    period_start: datetime
    period_end: datetime
    metadata: Dict[str, str]

class PaymentMethod(BaseModel):
    id: str
    customer_id: str
    type: str  # "card", "bank_account"
    details: Dict[str, str]
    is_default: bool

class UsageRecord(BaseModel):
    id: str
    subscription_id: str
    timestamp: datetime
    quantity: int
    action: str  # "increment", "set"
