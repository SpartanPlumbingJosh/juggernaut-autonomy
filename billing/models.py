from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

class PaymentMethod(str, Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"

class SubscriptionPlan(BaseModel):
    id: str
    name: str
    price_cents: int
    currency: str
    interval: str  # "month", "year"
    interval_count: int
    trial_period_days: Optional[int]
    metadata: Dict[str, Any]

class Subscription(BaseModel):
    id: str
    customer_id: str
    plan_id: str
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    created_at: datetime
    metadata: Dict[str, Any]

class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"

class Invoice(BaseModel):
    id: str
    customer_id: str
    subscription_id: Optional[str]
    amount_due_cents: int
    amount_paid_cents: int
    status: InvoiceStatus
    due_date: Optional[datetime]
    paid_at: Optional[datetime]
    created_at: datetime
    metadata: Dict[str, Any]

class PaymentIntentStatus(str, Enum):
    REQUIRES_PAYMENT_METHOD = "requires_payment_method"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REQUIRES_ACTION = "requires_action"
    PROCESSING = "processing"
    REQUIRES_CAPTURE = "requires_capture"
    CANCELED = "canceled"
    SUCCEEDED = "succeeded"

class PaymentIntent(BaseModel):
    id: str
    customer_id: str
    amount_cents: int
    currency: str
    status: PaymentIntentStatus
    payment_method: PaymentMethod
    created_at: datetime
    metadata: Dict[str, Any]

class Receipt(BaseModel):
    id: str
    payment_intent_id: str
    customer_id: str
    amount_cents: int
    currency: str
    created_at: datetime
    pdf_url: Optional[str]
    metadata: Dict[str, Any]
