from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
from pydantic import BaseModel

class BillingFrequency(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"
    USAGE = "usage"

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"

class SubscriptionPlan(BaseModel):
    id: str
    name: str
    description: str
    price_cents: int
    currency: str
    billing_frequency: BillingFrequency
    usage_limits: Optional[Dict[str, int]]
    features: List[str]
    metadata: Optional[Dict[str, str]]

class Subscription(BaseModel):
    id: str
    customer_id: str
    plan_id: str
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    metadata: Optional[Dict[str, str]]
    created_at: datetime
    updated_at: datetime

class Invoice(BaseModel):
    id: str
    subscription_id: str
    customer_id: str
    amount_due_cents: int
    currency: str
    status: str
    period_start: datetime
    period_end: datetime
    pdf_url: Optional[str]
    created_at: datetime
    paid_at: Optional[datetime]

class PaymentMethod(BaseModel):
    id: str
    customer_id: str
    type: str
    last4: str
    exp_month: int
    exp_year: int
    created_at: datetime
