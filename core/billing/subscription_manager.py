from typing import Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"

class SubscriptionManager:
    """Manage subscriptions, plans, and entitlements."""
    
    def __init__(self):
        self.plans = self._load_plans()
        
    def _load_plans(self) -> Dict[str, Any]:
        """Load subscription plans from config/database."""
        # TODO: Load from persistent storage
        return {
            "basic": {
                "id": "basic",
                "name": "Basic Plan",
                "price": 9900,  # in cents
                "currency": "usd",
                "interval": "month",
                "features": ["feature1", "feature2"]
            },
            "pro": {
                "id": "pro",
                "name": "Pro Plan",
                "price": 19900,
                "currency": "usd",
                "interval": "month",
                "features": ["feature1", "feature2", "feature3"]
            }
        }
        
    def create_subscription(self, customer_id: str, plan_id: str, trial_days: int = 0) -> Dict[str, Any]:
        """Create a new subscription."""
        plan = self.plans.get(plan_id)
        if not plan:
            raise ValueError(f"Invalid plan ID: {plan_id}")
            
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=30)  # Default monthly
        
        if trial_days > 0:
            end_date = start_date + timedelta(days=trial_days)
            
        return {
            "id": "sub_123",  # TODO: Generate unique ID
            "customer_id": customer_id,
            "plan_id": plan_id,
            "status": SubscriptionStatus.TRIALING.value if trial_days > 0 else SubscriptionStatus.ACTIVE.value,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "renewal_date": end_date.isoformat(),
            "plan_details": plan
        }
        
    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a subscription."""
        # TODO: Implement cancellation logic
        return {
            "id": subscription_id,
            "status": SubscriptionStatus.CANCELED.value,
            "cancelled_at": datetime.utcnow().isoformat()
        }
        
    def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Get subscription details."""
        # TODO: Implement retrieval from database
        pass
        
    def list_subscriptions(self, customer_id: str) -> List[Dict[str, Any]]:
        """List all subscriptions for a customer."""
        # TODO: Implement retrieval from database
        pass
