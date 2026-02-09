"""
Billing data models.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class Customer(BaseModel):
    id: str
    email: str
    name: str
    payment_method: str  # 'stripe' or 'paypal'
    payment_id: str  # Customer ID in payment provider
    tax_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class Invoice(BaseModel):
    id: str
    customer_id: str
    amount: float
    tax: float
    currency: str
    status: str  # 'draft', 'paid', 'overdue'
    due_date: datetime
    paid_at: Optional[datetime] = None
    payment_method: Optional[str] = None
    payment_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class Subscription(BaseModel):
    id: str
    customer_id: str
    plan_id: str
    status: str  # 'active', 'canceled', 'paused'
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    payment_method: str
    payment_id: str  # Subscription ID in payment provider
    created_at: datetime
    updated_at: datetime
