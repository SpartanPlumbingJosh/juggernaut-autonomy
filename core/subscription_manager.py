"""
Subscription Management - Handles subscription lifecycle including 
signup, renewals, upgrades/downgrades, and cancellations.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import uuid

class SubscriptionManager:
    """Manage customer subscriptions and recurring billing."""
    
    def __init__(self, billing_system, execute_sql: callable, log_action: callable):
        self.billing_system = billing_system
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    async def create_subscription(self, customer_id: str, plan_id: str, 
                                payment_method: str) -> Dict:
        """Create a new subscription for a customer."""
        sub_id = str(uuid.uuid4())
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=30)  # Monthly subscription
        
        await self.execute_sql(
            f"""
            INSERT INTO subscriptions (
                id, customer_id, plan_id, status,
                start_date, end_date, created_at
            ) VALUES (
                '{sub_id}', '{customer_id}', '{plan_id}', 
                'active', '{start_date.isoformat()}', 
                '{end_date.isoformat()}', NOW()
            )
            """
        )
        
        # Create initial invoice
        plan = await self.get_plan_details(plan_id)
        if plan:
            await self.billing_system.create_invoice(
                customer_id, plan["price_cents"],
                f"Subscription for {plan['name']}"
            )
        
        await self.log_action(
            "subscription.created",
            f"New subscription created for {customer_id}",
            level="info",
            output_data={"subscription_id": sub_id, "plan_id": plan_id}
        )
        
        return {"success": True, "subscription_id": sub_id}
        
    async def renew_subscription(self, subscription_id: str) -> Dict:
        """Renew an existing subscription."""
        sub = await self.get_subscription(subscription_id)
        if not sub:
            return {"success": False, "error": "Subscription not found"}
            
        new_end_date = sub["end_date"] + timedelta(days=30)
        
        await self.execute_sql(
            f"""
            UPDATE subscriptions
            SET end_date = '{new_end_date.isoformat()}',
                status = 'active',
                updated_at = NOW()
            WHERE id = '{subscription_id}'
            """
        )
        
        # Create renewal invoice
        plan = await self.get_plan_details(sub["plan_id"])
        if plan:
            await self.billing_system.create_invoice(
                sub["customer_id"], plan["price_cents"],
                f"Renewal for {plan['name']}"
            )
        
        await self.log_action(
            "subscription.renewed",
            f"Subscription {subscription_id} renewed",
            level="info",
            output_data={"subscription_id": subscription_id}
        )
        
        return {"success": True}
        
    async def cancel_subscription(self, subscription_id: str) -> Dict:
        """Cancel an active subscription."""
        await self.execute_sql(
            f"""
            UPDATE subscriptions
            SET status = 'cancelled',
                updated_at = NOW()
            WHERE id = '{subscription_id}'
            """
        )
        
        await self.log_action(
            "subscription.cancelled",
            f"Subscription {subscription_id} cancelled",
            level="info",
            output_data={"subscription_id": subscription_id}
        )
        
        return {"success": True}
        
    async def get_subscription(self, subscription_id: str) -> Optional[Dict]:
        """Get subscription details."""
        result = await self.execute_sql(
            f"""
            SELECT * FROM subscriptions
            WHERE id = '{subscription_id}'
            LIMIT 1
            """
        )
        return result.get("rows", [{}])[0]
        
    async def get_plan_details(self, plan_id: str) -> Optional[Dict]:
        """Get pricing plan details."""
        result = await self.execute_sql(
            f"""
            SELECT * FROM pricing_plans
            WHERE id = '{plan_id}'
            LIMIT 1
            """
        )
        return result.get("rows", [{}])[0]
