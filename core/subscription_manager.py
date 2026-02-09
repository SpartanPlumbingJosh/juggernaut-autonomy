from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"

class SubscriptionManager:
    """Manage subscription lifecycle and billing."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    async def create_subscription(self, customer_id: str, plan_id: str, trial_days: int = 0) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            start_date = datetime.utcnow()
            end_date = start_date + timedelta(days=30)  # Default monthly billing
            
            if trial_days > 0:
                end_date = start_date + timedelta(days=trial_days)
                status = SubscriptionStatus.TRIALING.value
            else:
                status = SubscriptionStatus.ACTIVE.value
                
            sql = f"""
            INSERT INTO subscriptions (
                id, customer_id, plan_id, status,
                start_date, end_date, trial_end,
                created_at, updated_at
            ) VALUES (
                gen_random_uuid(),
                '{customer_id}',
                '{plan_id}',
                '{status}',
                '{start_date.isoformat()}',
                '{end_date.isoformat()}',
                {f"'{end_date.isoformat()}'" if trial_days > 0 else "NULL"},
                NOW(),
                NOW()
            )
            RETURNING id
            """
            
            result = await self.execute_sql(sql)
            sub_id = result.get("rows", [{}])[0].get("id")
            
            if sub_id:
                return {"success": True, "subscription_id": sub_id}
            return {"success": False, "error": "Failed to create subscription"}
        except Exception as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel an existing subscription."""
        try:
            sql = f"""
            UPDATE subscriptions
            SET status = '{SubscriptionStatus.CANCELED.value}',
                updated_at = NOW()
            WHERE id = '{subscription_id}'
            """
            await self.execute_sql(sql)
            return {"success": True}
        except Exception as e:
            logger.error(f"Subscription cancellation failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def process_renewals(self) -> Dict[str, Any]:
        """Process subscription renewals."""
        try:
            # Get subscriptions due for renewal
            sql = """
            SELECT id, customer_id, plan_id
            FROM subscriptions
            WHERE end_date <= NOW()
              AND status IN ('active', 'trialing')
            LIMIT 100
            """
            result = await self.execute_sql(sql)
            subscriptions = result.get("rows", [])
            
            renewed = 0
            failures = []
            
            for sub in subscriptions:
                renewal_result = await self._renew_subscription(sub)
                if renewal_result.get("success"):
                    renewed += 1
                else:
                    failures.append({
                        "subscription_id": sub.get("id"),
                        "error": renewal_result.get("error")
                    })
                    
            return {
                "success": True,
                "renewed": renewed,
                "failures": failures
            }
        except Exception as e:
            logger.error(f"Subscription renewal processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def _renew_subscription(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Renew an individual subscription."""
        try:
            new_end_date = datetime.utcnow() + timedelta(days=30)
            sql = f"""
            UPDATE subscriptions
            SET end_date = '{new_end_date.isoformat()}',
                updated_at = NOW()
            WHERE id = '{subscription.get("id")}'
            """
            await self.execute_sql(sql)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
