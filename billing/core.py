from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional
import json
from enum import Enum

class BillingInterval(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"  
    ANNUALLY = "annually"

class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"

class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"

class BillingAddress:
    def __init__(self, country: str, city: str, line1: str, line2: str = "", postal_code: str = ""):
        self.country = country
        self.city = city
        self.line1 = line1
        self.line2 = line2
        self.postal_code = postal_code

class InvoiceItem:
    def __init__(self, 
                 amount: Decimal,
                 currency: Currency,
                 description: str,
                 period_start: Optional[datetime] = None,
                 period_end: Optional[datetime] = None):
        self.amount = amount
        self.currency = currency
        self.description = description
        self.period_start = period_start or datetime.now(timezone.utc)
        self.period_end = period_end
        
    def to_dict(self) -> Dict:
        return {
            "amount": str(self.amount),
            "currency": self.currency.value,
            "description": self.description,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None
        }

class Invoice:
    def __init__(self,
                 customer_id: str,
                 items: List[InvoiceItem],
                 status: InvoiceStatus = InvoiceStatus.DRAFT):
        self.customer_id = customer_id
        self.items = items
        self.status = status
        self.created_at = datetime.now(timezone.utc)
        self.due_date = datetime.now(timezone.utc) + timedelta(days=30)
        
    def total_amount(self) -> Dict[Currency, Decimal]:
        totals = {}
        for item in self.items:
            if item.currency not in totals:
                totals[item.currency] = Decimal(0)
            totals[item.currency] += item.amount
        return totals
        
    def to_dict(self) -> Dict:
        return {
            "customer_id": self.customer_id,
            "status": self.status.value,
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at.isoformat(),
            "due_date": self.due_date.isoformat(),
            "totals": {k.value: str(v) for k, v in self.total_amount().items()}
        }

class SubscriptionPlan:
    def __init__(self,
                 name: str,
                 interval: BillingInterval,
                 amount: Decimal,
                 currency: Currency,
                 description: str = ""):
        self.name = name
        self.interval = interval
        self.amount = amount
        self.currency = currency
        self.description = description
        
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "interval": self.interval.value,
            "amount": str(self.amount),
            "currency": self.currency.value,
            "description": self.description
        }
