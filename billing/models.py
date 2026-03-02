"""
Core billing models for revenue tracking.
Includes invoices, payments, subscriptions.
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional
import logging
from uuid import uuid4

class BillingFrequency(Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    ONE_TIME = "one_time"

class InvoiceStatus(Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"

class PaymentMethod(Enum):
    CARD = "card"
    ACH = "ach"
    WIRE = "wire"
    MANUAL = "manual"

class Invoice:
    def __init__(self, 
                 amount_due: float,
                 currency: str = "usd",
                 customer_id: str = "",
                 billing_status: InvoiceStatus = InvoiceStatus.DRAFT,
                 due_date: Optional[datetime] = None,
                 invoice_items: List[Dict] = None):
        self.id = str(uuid4())
        self.amount_due = amount_due
        self.currency = currency
        self.customer_id = customer_id
        self.status = billing_status
        self.created_at = datetime.utcnow()
        self.due_date = due_date or datetime.utcnow() + timedelta(days=15)
        self.items = invoice_items or []
        self.payments: List[Dict] = []
        self.logger = logging.getLogger(__name__)

    def add_payment(self, 
                   amount: float, 
                   method: PaymentMethod,
                   transaction_id: str,
                   payment_date: Optional[datetime] = None) -> None:
        """Record successful payment against invoice."""
        if amount > self.amount_due:
            raise ValueError("Payment exceeds invoice amount")
        
        payment = {
            "id": str(uuid4()),
            "amount": amount,
            "method": method.value,
            "transaction_id": transaction_id,
            "date": payment_date or datetime.utcnow()
        }
        self.payments.append(payment)
        self.amount_due -= amount
        
        if abs(self.amount_due) < 0.01:  # Handle floating point precision
            self.status = InvoiceStatus.PAID
            self.logger.info(f"Invoice {self.id} fully paid")

class SubscriptionPlan:
    def __init__(self, 
                 name: str,
                 amount: float,
                 frequency: BillingFrequency,
                 interval: int = 1,
                 currency: str = "usd",
                 description: str = ""):
        self.id = str(uuid4())
        self.name = name
        self.amount = amount
        self.currency = currency
        self.frequency = frequency
        self.interval = interval  # e.g. every 3 months for quarterly
        self.description = description
