"""
Payment system schemas and data models.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator

class CustomerCreate(BaseModel):
    email: str
    name: str
    metadata: Optional[dict] = None

class SubscriptionCreate(BaseModel):
    customer_id: str
    price_id: str
    trial_days: int = Field(default=0, ge=0)

class InvoiceCreate(BaseModel):
    customer_id: str
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    description: str
    metadata: Optional[dict] = None

class PaymentEvent(BaseModel):
    event_id: str
    event_type: str
    amount: float
    currency: str
    timestamp: datetime
    metadata: Optional[dict] = None

    @validator('event_type')
    def validate_event_type(cls, v):
        if v not in ['payment', 'refund', 'chargeback']:
            raise ValueError('Invalid event type')
        return v

class WebhookPayload(BaseModel):
    payload: str
    signature: str
    timestamp: datetime

class SubscriptionDetails(BaseModel):
    subscription_id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
