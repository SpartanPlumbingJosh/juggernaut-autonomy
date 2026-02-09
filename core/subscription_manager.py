from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging
from core.database import query_db

class SubscriptionManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def create_subscription(self, customer_id: str, plan_id: str, start_date: Optional[datetime] = None) -> Dict:
        """Create a new subscription in the system."""
        start_date = start_date or datetime.utcnow()
        end_date = start_date + timedelta(days=30)  # Monthly subscription
        
        try:
            await query_db(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, 
                    start_date, end_date, status,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{plan_id}',
                    '{start_date.isoformat()}',
                    '{end_date.isoformat()}',
                    'active',
                    NOW(),
                    NOW()
                )
                RETURNING *
                """
            )
            return {"success": True}
        except Exception as e:
            self.logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}

    async def cancel_subscription(self, subscription_id: str) -> Dict:
        """Cancel an existing subscription."""
        try:
            await query_db(
                f"""
                UPDATE subscriptions
                SET status = 'cancelled',
                    end_date = NOW(),
                    updated_at = NOW()
                WHERE id = '{subscription_id}'
                """
            )
            return {"success": True}
        except Exception as e:
            self.logger.error(f"Failed to cancel subscription: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_active_subscriptions(self, customer_id: str) -> List[Dict]:
        """Get all active subscriptions for a customer."""
        try:
            result = await query_db(
                f"""
                SELECT *
                FROM subscriptions
                WHERE customer_id = '{customer_id}'
                  AND status = 'active'
                  AND end_date > NOW()
                """
            )
            return result.get("rows", [])
        except Exception as e:
            self.logger.error(f"Failed to get subscriptions: {str(e)}")
            return []

    async def renew_subscriptions(self) -> Dict:
        """Automatically renew subscriptions that are due."""
        try:
            result = await query_db(
                """
                UPDATE subscriptions
                SET end_date = end_date + INTERVAL '1 month',
                    updated_at = NOW()
                WHERE status = 'active'
                  AND end_date <= NOW() + INTERVAL '3 days'
                RETURNING *
                """
            )
            return {"success": True, "renewed": len(result.get("rows", []))}
        except Exception as e:
            self.logger.error(f"Failed to renew subscriptions: {str(e)}")
            return {"success": False, "error": str(e)}
