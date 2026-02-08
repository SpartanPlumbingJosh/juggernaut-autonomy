"""
Billing data models with strict validation for financial data integrity.
"""

from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List, Dict
from decimal import Decimal
from enum import Enum

class Address(BaseModel):
    line1: str
    line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str

class Customer(BaseModel):
    id: str
    email: str
    name: str
    tax_id: Optional[str] = None
    billing_address: Optional[Address] = None
    created_at: datetime
    updated_at: datetime

class Plan(BaseModel):
    id: str
    name: str 
    description: str
    billing_cycle: str  # "monthly", "yearly", etc.
    amount_cents: int
    currency: str = "USD"
    features: List[str] = []
    metadata: Dict = {}

class Subscription(BaseModel):
    id: str
    customer_id: str
    plan_id: str
    status: str  # "active", "canceled", etc.
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    created_at: datetime
    updated_at: datetime

class Invoice(BaseModel):
    id: str
    customer_id: str
    subscription_id: str
    amount_due_cents: int
    amount_paid_cents: int = 0
    status: str  # "paid", "open", etc.
    due_date: datetime
    paid_at: Optional[datetime] = None
    lines: List[Dict] = []
    metadata: Dict = {}

class PaymentMethod(BaseModel):
    id: str
    customer_id: str
    type: str  # "card", "bank", etc.
    last4: Optional[str] = None
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None
    is_default: bool = False
    created_at: datetime
    updated_at: datetime
