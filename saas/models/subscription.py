from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel

class SubscriptionPlan(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAUSED = "paused"
    TRIAL = "trial"

class Subscription(BaseModel):
    id: str
    user_id: str
    plan: SubscriptionPlan
    status: SubscriptionStatus
    start_date: datetime
    end_date: Optional[datetime] = None
    renewal_date: Optional[datetime] = None
    payment_method_id: Optional[str] = None
    price_cents: int
    currency: str = "USD"

class SubscriptionCreate(BaseModel):
    user_id: str
    plan: SubscriptionPlan
    payment_method_id: str
    price_cents: int
    currency: str = "USD"

class SubscriptionUpdate(BaseModel):
    plan: Optional[SubscriptionPlan] = None
    status: Optional[SubscriptionStatus] = None
    end_date: Optional[datetime] = None
    renewal_date: Optional[datetime] = None
