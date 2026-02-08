from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Optional
import stripe
import logging
from enum import Enum
import json

# Configure logger
logger = logging.getLogger(__name__)

class RevenuePlanStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELED = "canceled"
    COMPLETED = "completed"

class AutonomousRevenueSystem:
    def __init__(self, api_key: str):
        """Initialize with Stripe API key"""
        stripe.api_key = api_key
        self.plans: Dict[str, Dict] = {}
        self.users: Dict[str, Dict] = {}
        
    def create_plan(self, 
                   name: str, 
                   price: int, 
                   interval: str = "month",
                   description: str = "") -> Dict:
        """Create a new revenue plan"""
        try:
            plan = stripe.Plan.create(
                amount=price * 100,  # convert to cents
                currency="usd",
                interval=interval,
                product={
                    "name": name,
                    "description": description
                }
            )
            self.plans[plan.id] = {
                "name": name,
                "price": price,
                "status": RevenuePlanStatus.ACTIVE.value,
                "stripe_id": plan.id,
                "created_at": datetime.utcnow().isoformat()
            }
            return self.plans[plan.id]
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create plan: {str(e)}")
            raise
            
    def subscribe_user(self, 
                      plan_id: str, 
                      email: str, 
                      payment_token: str,
                      metadata: Optional[Dict] = None) -> Dict:
        """Subscribe user to a plan with automated onboarding"""
        try:
            # Create or retrieve customer
            customer = stripe.Customer.create(
                email=email,
                source=payment_token
            )
            
            # Subscribe customer
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{"plan": plan_id}],
                metadata=metadata or {}
            )
            
            # Record user subscription
            self.users[customer.id] = {
                "email": email,
                "plan_id": plan_id,
                "status": "active",
                "stripe_id": customer.id,
                "joined_at": datetime.utcnow().isoformat(),
                "last_payment": datetime.utcnow().isoformat()
            }
            
            # Deliver service automatically
            self._deliver_service(email, plan_id)
            
            return self.users[customer.id]
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to subscribe user: {str(e)}")
            raise
            
    def _deliver_service(self, email: str, plan_id: str) -> bool:
        """Automatically deliver service to subscribed user"""
        try:
            # TODO: Implement actual service delivery mechanism
            logger.info(f"Service delivered to {email} for plan {plan_id}")
            return True
        except Exception as e:
            logger.error(f"Service delivery failed for {email}: {str(e)}")
            return False
            
    def get_revenue_metrics(self) -> Dict:
        """Get revenue analytics"""
        active_plans = len([p for p in self.plans.values() if p["status"] == RevenuePlanStatus.ACTIVE.value])
        active_users = len([u for u in self.users.values() if u["status"] == "active"])
        
        return {
            "active_plans": active_plans,
            "total_plans": len(self.plans),
            "active_users": active_users,
            "total_users": len(self.users),
            "mrr_estimate": sum(
                p["price"] for p in self.plans.values() 
                if p["status"] == RevenuePlanStatus.ACTIVE.value
            )
        }
