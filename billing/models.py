"""
Data models for billing and subscriptions.
"""

from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
from pydantic import BaseModel

class SubscriptionStatus(str, Enum):
    ACTIVE = 'active'
    CANCELED = 'canceled'
    PAST_DUE = 'past_due'
    UNPAID = 'unpaid'
    TRIALING = 'trialing'

class PaymentMethod(str, Enum):
    STRIPE = 'stripe'
    PAYPAL = 'paypal'
    BANK_TRANSFER = 'bank_transfer'

class BillingAddress(BaseModel):
    line1: str
    line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str

class Customer(BaseModel):
    id: str
    user_id: str
    email: str
    name: str
    payment_method: PaymentMethod
    billing_address: Optional[BillingAddress] = None
    created_at: datetime
    updated_at: datetime

class SubscriptionPlan(BaseModel):
    id: str
    name: str
    description: str
    price_id: str  # Stripe/PayPal price ID
    amount: int  # in cents
    currency: str
    billing_cycle: str  # monthly/yearly
    features: List[str]
    is_active: bool

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
    subscription_id: str
    amount: int
    currency: str
    status: str
    due_date: datetime
    paid_at: Optional[datetime]
    invoice_pdf: str  # URL to PDF
    metadata: Dict[str, str]
