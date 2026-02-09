"""
Database models for billing system.
"""

from datetime import datetime
from typing import Optional, List, Dict
from dataclasses import dataclass

@dataclass
class Customer:
    id: str
    email: str
    name: str
    stripe_id: Optional[str] = None
    paypal_id: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: Optional[Dict] = None

@dataclass
class Subscription:
    id: str
    customer_id: str
    plan_id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    created_at: Optional[datetime] = None

@dataclass
class Invoice:
    id: str
    customer_id: str
    amount: int
    currency: str
    status: str
    due_date: datetime
    paid_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

@dataclass
class PaymentMethod:
    id: str
    customer_id: str
    type: str  # card, paypal, etc.
    details: Dict
    is_default: bool = False
    created_at: Optional[datetime] = None

@dataclass
class Transaction:
    id: str
    customer_id: str
    amount: int
    currency: str
    status: str
    payment_method: str
    transaction_id: str
    created_at: Optional[datetime] = None
    metadata: Optional[Dict] = None
