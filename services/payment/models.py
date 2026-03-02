from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class PaymentMethod(BaseModel):
    """Payment method details."""
    id: str
    type: str  # card, paypal, crypto, etc.
    details: Dict[str, Any]
    is_default: bool = False
    created_at: datetime = datetime.utcnow()

class PaymentIntent(BaseModel):
    """Payment intent model."""
    id: str
    amount: int  # in smallest currency unit (cents/satoshi/etc)
    currency: str
    status: str
    payment_method: Optional[PaymentMethod] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime = datetime.utcnow()

class Subscription(BaseModel):
    """Subscription model."""
    id: str
    plan_id: str
    customer_id: str
    status: str
    current_period_end: datetime
    payment_method: Optional[PaymentMethod] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime = datetime.utcnow()

class Invoice(BaseModel):
    """Invoice model."""
    id: str
    number: str
    customer_id: str
    amount_due: int
    currency: str
    status: str
    items: List[Dict[str, Any]]
    due_date: datetime
    metadata: Dict[str, Any] = {}
    created_at: datetime = datetime.utcnow()

class WebhookEvent(BaseModel):
    """Webhook event model."""
    id: str
    type: str
    data: Dict[str, Any]
    created_at: datetime
    processor: str
