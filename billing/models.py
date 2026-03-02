from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List
from pydantic import BaseModel

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"

class PaymentMethod(str, Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"

class SubscriptionPlan(BaseModel):
    id: str
    name: str
    description: str
    price_cents: int
    currency: str
    billing_interval: str  # "month" or "year"
    features: List[str]

class Subscription(BaseModel):
    id: str
    customer_id: str
    plan_id: str
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    payment_method: PaymentMethod
    metadata: Optional[Dict] = None

class Invoice(BaseModel):
    id: str
    customer_id: str
    subscription_id: Optional[str]
    amount_cents: int
    currency: str
    status: str
    due_date: datetime
    paid_at: Optional[datetime]
    payment_method: PaymentMethod
    metadata: Optional[Dict] = None

class Payment(BaseModel):
    id: str
    invoice_id: str
    amount_cents: int
    currency: str
    payment_method: PaymentMethod
    processed_at: datetime
    status: str
    failure_reason: Optional[str]
    metadata: Optional[Dict] = None

class Customer(BaseModel):
    id: str
    email: str
    name: str
    payment_method: PaymentMethod
    created_at: datetime
    metadata: Optional[Dict] = None
