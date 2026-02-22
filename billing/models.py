from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict
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
    description: str
    price_cents: int
    currency: str
    billing_interval: str  # "month" or "year"
    features: Dict[str, bool]
    metadata: Dict[str, str]

class Subscription(BaseModel):
    id: str
    customer_id: str
    plan_id: str
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, str]

class Invoice(BaseModel):
    id: str
    customer_id: str
    subscription_id: Optional[str]
    amount_due_cents: int
    amount_paid_cents: int
    currency: str
    status: str  # "paid", "open", "void", "uncollectible"
    created_at: datetime
    due_date: datetime
    payment_intent_id: Optional[str]
    metadata: Dict[str, str]

class PaymentMethod(BaseModel):
    id: str
    customer_id: str
    type: str  # "card", "bank_account", etc
    details: Dict[str, str]
    is_default: bool
    created_at: datetime
    updated_at: datetime

class Customer(BaseModel):
    id: str
    email: str
    name: Optional[str]
    phone: Optional[str]
    address: Optional[Dict[str, str]]
    tax_id: Optional[str]
    currency: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, str]
