from datetime import datetime, timedelta
from typing import Dict, Optional

class SubscriptionService:
    """Manages user subscriptions and billing logic."""
    
    @staticmethod
    async def get_user_subscription(user_id: str) -> Optional[Dict]:
        """Get active subscription for user."""
        sql = """
        SELECT s.*, p.name as plan_name, p.features
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.id
        WHERE s.user_id = %(user_id)s
        AND s.status = 'active'
        AND (s.ends_at IS NULL OR s.ends_at > NOW())
        LIMIT 1
        """
        result = await query_db(sql, {"user_id": user_id})
        return result.get("rows", [{}])[0] or None

    @staticmethod
    async def update_billing_cycle(subscription_id: str) -> Dict:
        """Handle recurring billing cycle."""
        sql = """
        UPDATE subscriptions 
        SET 
            last_billed_at = NOW(),
            next_billing_at = NOW() + interval '1 month',
            billing_cycles = billing_cycles + 1
        WHERE id = %(subscription_id)s
        RETURNING *
        """
        return await query_db(sql, {"subscription_id": subscription_id})
