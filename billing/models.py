from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, List
from pydantic import BaseModel, Field, validator
from decimal import Decimal

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIAL = "trial"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"

class PaymentMethod(str, Enum):
    CARD = "card"
    BANK = "bank"
    PAYPAL = "paypal"

class SubscriptionPlan(BaseModel):
    id: str
    name: str
    description: str
    price: Decimal
    currency: str = "USD"
    billing_cycle: str = "monthly"
    trial_period_days: int = 0
    metadata: Dict[str, str] = {}

class Subscription(BaseModel):
    id: str
    customer_id: str
    plan_id: str
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    canceled_at: Optional[datetime] = None
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    payment_method: PaymentMethod
    metadata: Dict[str, str] = {}

class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"

class Invoice(BaseModel):
    id: str
    subscription_id: str
    customer_id: str
    amount_due: Decimal
    amount_paid: Decimal
    currency: str = "USD"
    status: InvoiceStatus
    due_date: datetime
    period_start: datetime
    period_end: datetime
    payment_intent_id: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None
    metadata: Dict[str, str] = {}

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
    amount: Decimal
    currency: str = "USD"
    status: PaymentIntentStatus
    customer_id: str
    payment_method: PaymentMethod
    invoice_id: Optional[str] = None
    metadata: Dict[str, str] = {}
