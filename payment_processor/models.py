from datetime import datetime
from typing import Optional, Dict, List
from pydantic import BaseModel

class Customer(BaseModel):
    id: str
    email: str
    name: str
    metadata: Optional[Dict] = None
    created_at: datetime
    updated_at: datetime

class Subscription(BaseModel):
    id: str
    customer_id: str
    plan_id: str
    status: str
    start_date: datetime
    end_date: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    metadata: Optional[Dict] = None

class Payment(BaseModel):
    id: str
    customer_id: str
    amount: float
    currency: str
    status: str
    payment_method: str
    created_at: datetime

class Invoice(BaseModel):
    id: str
    customer_id: str
    amount_due: float
    amount_paid: float
    currency: str
    status: str
    due_date: datetime
    paid_at: Optional[datetime] = None
    metadata: Optional[Dict] = None

class WebhookEvent(BaseModel):
    id: str
    type: str
    data: Dict
    created_at: datetime
