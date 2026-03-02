from datetime import datetime, timedelta
from typing import Dict, List, Optional
from core.database import query_db

class SubscriptionManager:
    def __init__(self):
        self.plans = {
            'basic': {
                'price_cents': 9900,
                'interval': 'month',
                'features': ['feature1', 'feature2']
            },
            'pro': {
                'price_cents': 19900,
                'interval': 'month',
                'features': ['feature1', 'feature2', 'feature3']
            }
        }

    async def create_subscription(self, user_id: str, plan_id: str, payment_method: str) -> Dict[str, Any]:
        """Create a new subscription for a user"""
        plan = self.plans.get(plan_id)
        if not plan:
            raise ValueError("Invalid plan ID")

        # Create subscription in database
        result = await query_db(f"""
            INSERT INTO subscriptions (
                id, user_id, plan_id, status, 
                start_date, end_date, created_at
            ) VALUES (
                gen_random_uuid(),
                '{user_id}',
                '{plan_id}',
                'active',
                NOW(),
                NOW() + INTERVAL '1 {plan['interval']}',
                NOW()
            )
            RETURNING id
        """)
        return {'subscription_id': result['rows'][0]['id']}

    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel an existing subscription"""
        await query_db(f"""
            UPDATE subscriptions
            SET status = 'cancelled',
                end_date = NOW()
            WHERE id = '{subscription_id}'
        """)
        return {'status': 'cancelled'}

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Get subscription details"""
        result = await query_db(f"""
            SELECT * FROM subscriptions
            WHERE id = '{subscription_id}'
        """)
        return result['rows'][0] if result['rows'] else None

    async def renew_subscriptions(self) -> Dict[str, Any]:
        """Automatically renew active subscriptions"""
        result = await query_db("""
            SELECT * FROM subscriptions
            WHERE status = 'active'
            AND end_date <= NOW()
        """)
        
        renewed = 0
        for sub in result['rows']:
            plan = self.plans.get(sub['plan_id'])
            if plan:
                await query_db(f"""
                    UPDATE subscriptions
                    SET end_date = NOW() + INTERVAL '1 {plan['interval']}'
                    WHERE id = '{sub['id']}'
                """)
                renewed += 1
                
        return {'renewed': renewed}

    async def get_user_subscriptions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all subscriptions for a user"""
        result = await query_db(f"""
            SELECT * FROM subscriptions
            WHERE user_id = '{user_id}'
        """)
        return result['rows']
