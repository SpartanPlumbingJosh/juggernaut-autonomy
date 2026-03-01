from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import uuid

class BillingType(Enum):
    SUBSCRIPTION = 'subscription'
    USAGE_BASED = 'usage'
    ONE_TIME = 'one_time'

class InvoiceStatus(Enum):
    DRAFT = 'draft'
    OPEN = 'open'
    PAID = 'paid'
    VOID = 'void'
    UNCOLLECTIBLE = 'uncollectible'

class PaymentStatus(Enum):
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'
    REFUNDED = 'refunded'

@dataclass
class Plan:
    id: str
    name: str
    billing_type: BillingType
    amount_cents: int
    currency: str
    interval: Optional[str] = None  # month, year etc for subscriptions
    usage_terms: Optional[Dict] = None  # For usage-based plans
    
@dataclass
class Invoice:
    id: str
    customer_id: str
    amount_cents: int
    currency: str
    status: InvoiceStatus
    due_date: datetime
    items: List[Dict]
    tax_amount_cents: Optional[int] = None
    metadata: Optional[Dict] = None
    
@dataclass
class PaymentMethod:
    id: str
    customer_id: str
    provider: str  # stripe, PayPal etc
    details: Dict[str, Any]
    is_default: bool = False
    
@dataclass 
class Subscription:
    id: str
    customer_id: str
    plan_id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    metadata: Optional[Dict] = None
    
@dataclass
class Payment:
    id: str
    invoice_id: str
    amount_cents: int
    currency: str
    status: PaymentStatus
    provider_id: Optional[str] = None  # Payment processor reference
    processed_at: Optional[datetime] = None
