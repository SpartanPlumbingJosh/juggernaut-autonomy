from typing import Dict, Optional
from datetime import datetime, timedelta
from core.database import query_db, execute_sql

class SubscriptionManager:
    """Manages customer subscriptions and billing cycles."""
    
    async def create_subscription(self, customer_id: str, plan_id: str, 
                                payment_method_id: str) -> Dict:
        """Create a new subscription."""
        try:
            # Get plan details
            plan = await query_db(
                f"SELECT * FROM billing_plans WHERE id = '{plan_id}'"
            )
            if not plan.get("rows"):
                return {"success": False, "error": "Plan not found"}
                
            plan_data = plan.get("rows")[0]
            
            # Create subscription record
            await execute_sql(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status, 
                    current_period_start, current_period_end,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{plan_id}',
                    'active',
                    NOW(),
                    NOW() + INTERVAL '{plan_data.get("billing_interval")}',
                    NOW(),
                    NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def renew_subscription(self, subscription_id: str) -> Dict:
        """Renew an existing subscription."""
        try:
            sub = await query_db(
                f"SELECT * FROM subscriptions WHERE id = '{subscription_id}'"
            )
            if not sub.get("rows"):
                return {"success": False, "error": "Subscription not found"}
                
            sub_data = sub.get("rows")[0]
            plan = await query_db(
                f"SELECT * FROM billing_plans WHERE id = '{sub_data.get("plan_id")}'"
            )
            plan_data = plan.get("rows")[0]
            
            await execute_sql(
                f"""
                UPDATE subscriptions SET
                    current_period_start = NOW(),
                    current_period_end = NOW() + INTERVAL '{plan_data.get("billing_interval")}',
                    updated_at = NOW()
                WHERE id = '{subscription_id}'
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
