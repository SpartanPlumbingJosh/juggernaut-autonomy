from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    TRIAL = "trial"
    PAST_DUE = "past_due"

class SubscriptionPlan:
    def __init__(self, id: str, name: str, price_cents: int, interval: str, features: Dict[str, Any]):
        self.id = id
        self.name = name
        self.price_cents = price_cents
        self.interval = interval
        self.features = features

class Subscription:
    def __init__(self, 
                 id: str,
                 user_id: str,
                 plan: SubscriptionPlan,
                 status: SubscriptionStatus,
                 start_date: datetime,
                 end_date: Optional[datetime] = None,
                 trial_end: Optional[datetime] = None):
        self.id = id
        self.user_id = user_id
        self.plan = plan
        self.status = status
        self.start_date = start_date
        self.end_date = end_date
        self.trial_end = trial_end

    def is_active(self) -> bool:
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]

    def days_remaining(self) -> int:
        if not self.end_date:
            return 0
        return (self.end_date - datetime.now()).days
