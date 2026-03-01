from datetime import datetime, timedelta
from typing import Dict, Optional
from enum import Enum

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"

class SubscriptionManager:
    def __init__(self):
        self.trial_period_days = 14

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method_id: str) -> Dict:
        """Create a new subscription"""
        try:
            # Create subscription in Stripe
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"plan": plan_id}],
                default_payment_method=payment_method_id,
                trial_period_days=self.trial_period_days
            )
            
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def cancel_subscription(self, subscription_id: str) -> Dict:
        """Cancel an existing subscription"""
        try:
            subscription = stripe.Subscription.delete(subscription_id)
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def update_subscription(self, subscription_id: str, plan_id: str) -> Dict:
        """Update subscription plan"""
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                items=[{"plan": plan_id}]
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_subscription(self, subscription_id: str) -> Dict:
        """Get subscription details"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "plan_id": subscription.plan.id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_subscription_webhook(self, event: Dict) -> Dict:
        """Process subscription webhook events"""
        event_type = event['type']
        data = event['data']['object']
        
        if event_type == 'customer.subscription.created':
            return self._handle_subscription_created(data)
        elif event_type == 'customer.subscription.updated':
            return self._handle_subscription_updated(data)
        elif event_type == 'customer.subscription.deleted':
            return self._handle_subscription_deleted(data)
        else:
            return {"success": True, "event": event_type}

    def _handle_subscription_created(self, data) -> Dict:
        """Handle new subscription"""
        return {"success": True, "event": "subscription_created"}

    def _handle_subscription_updated(self, data) -> Dict:
        """Handle subscription update"""
        return {"success": True, "event": "subscription_updated"}

    def _handle_subscription_deleted(self, data) -> Dict:
        """Handle subscription cancellation"""
        return {"success": True, "event": "subscription_deleted"}
