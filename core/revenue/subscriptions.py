from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
import json

from core.database import query_db, execute_db

class SubscriptionManager:
    """Manage subscription lifecycle and billing cycles."""
    
    async def create_subscription(self, plan_id: str, customer_id: str, start_date: Optional[datetime] = None) -> Dict:
        """Create a new subscription."""
        start_date = start_date or datetime.now(timezone.utc)
        sub_id = str(uuid.uuid4())
        
        await execute_db(
            f"""
            INSERT INTO subscriptions (
                id, plan_id, customer_id, status,
                start_date, current_period_start,
                current_period_end, created_at
            ) VALUES (
                '{sub_id}', '{plan_id}', '{customer_id}', 'active',
                '{start_date.isoformat()}', '{start_date.isoformat()}',
                '{(start_date + timedelta(days=30)).isoformat()}', NOW()
            )
            """
        )
        return {"id": sub_id, "status": "active"}

    async def renew_subscription(self, subscription_id: str) -> Dict:
        """Renew subscription for next period."""
        sub = await query_db(
            f"SELECT * FROM subscriptions WHERE id = '{subscription_id}'"
        )
        if not sub.get('rows'):
            raise ValueError("Subscription not found")
            
        current_period_end = datetime.fromisoformat(sub['rows'][0]['current_period_end'])
        new_period_end = current_period_end + timedelta(days=30)
        
        await execute_db(
            f"""
            UPDATE subscriptions 
            SET current_period_start = '{current_period_end.isoformat()}',
                current_period_end = '{new_period_end.isoformat()}',
                updated_at = NOW()
            WHERE id = '{subscription_id}'
            """
        )
        return {"id": subscription_id, "new_period_end": new_period_end.isoformat()}

    async def cancel_subscription(self, subscription_id: str, effective_date: Optional[datetime] = None) -> Dict:
        """Cancel subscription."""
        effective_date = effective_date or datetime.now(timezone.utc)
        
        await execute_db(
            f"""
            UPDATE subscriptions 
            SET status = 'canceled',
                canceled_at = '{effective_date.isoformat()}',
                updated_at = NOW()
            WHERE id = '{subscription_id}'
            """
        )
        return {"id": subscription_id, "status": "canceled"}
