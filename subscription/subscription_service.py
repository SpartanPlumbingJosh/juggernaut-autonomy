from datetime import datetime, timedelta
from typing import Dict, Optional
from enum import Enum

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    TRIAL = "trial"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

class SubscriptionService:
    def __init__(self):
        self.subscriptions_db = {}  # Replace with actual DB connection

    def create_subscription(self, user_id: str, plan_id: str) -> Dict:
        subscription = {
            "user_id": user_id,
            "plan_id": plan_id,
            "status": SubscriptionStatus.ACTIVE.value,
            "start_date": datetime.utcnow(),
            "end_date": datetime.utcnow() + timedelta(days=30),
            "auto_renew": True
        }
        self.subscriptions_db[user_id] = subscription
        return subscription

    def cancel_subscription(self, user_id: str) -> Optional[Dict]:
        subscription = self.subscriptions_db.get(user_id)
        if not subscription:
            return None
        
        subscription["status"] = SubscriptionStatus.CANCELLED.value
        subscription["auto_renew"] = False
        return subscription

    def get_subscription(self, user_id: str) -> Optional[Dict]:
        return self.subscriptions_db.get(user_id)

    def update_subscription_status(self, user_id: str, status: SubscriptionStatus) -> Optional[Dict]:
        subscription = self.subscriptions_db.get(user_id)
        if not subscription:
            return None
        
        subscription["status"] = status.value
        return subscription
