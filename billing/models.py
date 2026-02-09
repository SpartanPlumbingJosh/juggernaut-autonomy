from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

class SubscriptionStatus(Enum):
    ACTIVE = 'active'
    TRIALING = 'trialing'
    PAST_DUE = 'past_due'
    CANCELED = 'canceled'
    UNPAID = 'unpaid'

class PaymentMethod(Enum):
    CARD = 'card'
    BANK = 'bank'
    PAYPAL = 'paypal'
    OTHER = 'other'

class Customer:
    """Customer billing information"""
    
    def __init__(self, 
                 customer_id: str,
                 email: str,
                 name: Optional[str] = None,
                 payment_method: Optional[PaymentMethod] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.customer_id = customer_id
        self.email = email
        self.name = name
        self.payment_method = payment_method
        self.metadata = metadata or {}
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'customer_id': self.customer_id,
            'email': self.email,
            'name': self.name,
            'payment_method': self.payment_method.value if self.payment_method else None,
            'metadata': self.metadata
        }

class Subscription:
    """Subscription details"""
    
    def __init__(self,
                 subscription_id: str,
                 customer_id: str,
                 plan_id: str,
                 status: SubscriptionStatus,
                 current_period_start: datetime,
                 current_period_end: datetime,
                 cancel_at_period_end: bool = False,
                 metadata: Optional[Dict[str, Any]] = None):
        self.subscription_id = subscription_id
        self.customer_id = customer_id
        self.plan_id = plan_id
        self.status = status
        self.current_period_start = current_period_start
        self.current_period_end = current_period_end
        self.cancel_at_period_end = cancel_at_period_end
        self.metadata = metadata or {}
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'subscription_id': self.subscription_id,
            'customer_id': self.customer_id,
            'plan_id': self.plan_id,
            'status': self.status.value,
            'current_period_start': self.current_period_start.isoformat(),
            'current_period_end': self.current_period_end.isoformat(),
            'cancel_at_period_end': self.cancel_at_period_end,
            'metadata': self.metadata
        }

class Invoice:
    """Billing invoice"""
    
    def __init__(self,
                 invoice_id: str,
                 customer_id: str,
                 amount_due: int,
                 currency: str,
                 status: str,
                 period_start: datetime,
                 period_end: datetime,
                 paid: bool = False,
                 metadata: Optional[Dict[str, Any]] = None):
        self.invoice_id = invoice_id
        self.customer_id = customer_id
        self.amount_due = amount_due
        self.currency = currency
        self.status = status
        self.period_start = period_start
        self.period_end = period_end
        self.paid = paid
        self.metadata = metadata or {}
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'invoice_id': self.invoice_id,
            'customer_id': self.customer_id,
            'amount_due': self.amount_due,
            'currency': self.currency,
            'status': self.status,
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'paid': self.paid,
            'metadata': self.metadata
        }
