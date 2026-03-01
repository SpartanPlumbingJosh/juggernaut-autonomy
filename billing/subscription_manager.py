"""
Subscription Management - Handle recurring billing and subscription lifecycle.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

class SubscriptionManager:
    def __init__(self):
        self.subscriptions = {}
        
    async def create_subscription(self, customer_id: str, plan_id: str, payment_method_id: str) -> Dict[str, Any]:
        """Create a new subscription."""
        sub_id = f"sub_{len(self.subscriptions) + 1}"
        self.subscriptions[sub_id] = {
            "id": sub_id,
            "customer_id": customer_id,
            "plan_id": plan_id,
            "status": "active",
            "current_period_start": datetime.utcnow(),
            "current_period_end": datetime.utcnow() + timedelta(days=30),
            "payment_method_id": payment_method_id
        }
        return self.subscriptions[sub_id]
        
    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel an active subscription."""
        if subscription_id in self.subscriptions:
            self.subscriptions[subscription_id]["status"] = "canceled"
            self.subscriptions[subscription_id]["canceled_at"] = datetime.utcnow()
        return self.subscriptions.get(subscription_id, {})
        
    async def list_subscriptions(self, customer_id: str) -> List[Dict[str, Any]]:
        """List all subscriptions for a customer."""
        return [sub for sub in self.subscriptions.values() if sub["customer_id"] == customer_id]
