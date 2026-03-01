from typing import Dict, Optional
from datetime import datetime
from fastapi import HTTPException
from core.database import query_db

class SubscriptionManager:
    @staticmethod
    async def create_subscription(user_id: str, plan_id: str, stripe_subscription_id: str) -> Dict:
        try:
            result = await query_db(
                f"""
                INSERT INTO subscriptions (
                    user_id, plan_id, stripe_subscription_id, status, start_date, end_date
                ) VALUES (
                    '{user_id}', '{plan_id}', '{stripe_subscription_id}', 'active', NOW(), NULL
                )
                RETURNING *
                """
            )
            return result.get("rows", [{}])[0]
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def get_active_subscription(user_id: str) -> Optional[Dict]:
        try:
            result = await query_db(
                f"""
                SELECT * FROM subscriptions
                WHERE user_id = '{user_id}'
                AND status = 'active'
                AND (end_date IS NULL OR end_date > NOW())
                LIMIT 1
                """
            )
            return result.get("rows", [{}])[0] if result.get("rows") else None
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def cancel_subscription(subscription_id: str) -> Dict:
        try:
            result = await query_db(
                f"""
                UPDATE subscriptions
                SET status = 'canceled', end_date = NOW()
                WHERE id = '{subscription_id}'
                RETURNING *
                """
            )
            return result.get("rows", [{}])[0]
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
