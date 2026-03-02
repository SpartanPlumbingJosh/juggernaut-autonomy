from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum
from pydantic import BaseModel

class PaymentMethodType(str, Enum):
    CARD = "card"
    PAYPAL = "paypal"
    BANK = "bank"

class PaymentMethod(BaseModel):
    id: str
    type: PaymentMethodType
    last4: Optional[str]
    brand: Optional[str]
    email: Optional[str]
    created_at: datetime
    is_default: bool

class SubscriptionPlan(BaseModel):
    id: str
    name: str
    description: str
    price_cents: int
    currency: str
    billing_interval: str  # "month", "year"
    trial_period_days: int

class Subscription(BaseModel):
    id: str
    plan_id: str
    status: str  # "active", "canceled", "past_due"
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    payment_method_id: Optional[str]
    created_at: datetime
    updated_at: datetime

class Invoice(BaseModel):
    id: str
    subscription_id: str
    amount_due_cents: int
    amount_paid_cents: int
    currency: str
    status: str  # "paid", "open", "void"
    due_date: datetime
    paid_at: Optional[datetime]
    tax_cents: int
    total_cents: int
    invoice_pdf: Optional[str]
    created_at: datetime
