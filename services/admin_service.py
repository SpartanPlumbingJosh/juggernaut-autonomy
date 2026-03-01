from typing import Dict, List
from fastapi import HTTPException
from core.database import query_db

class AdminService:
    @staticmethod
    async def get_all_users() -> List[Dict]:
        try:
            result = await query_db("SELECT * FROM users")
            return result.get("rows", [])
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def get_all_subscriptions() -> List[Dict]:
        try:
            result = await query_db("SELECT * FROM subscriptions")
            return result.get("rows", [])
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def get_payment_history(user_id: str) -> List[Dict]:
        try:
            result = await query_db(
                f"""
                SELECT * FROM payments
                WHERE user_id = '{user_id}'
                ORDER BY created_at DESC
                """
            )
            return result.get("rows", [])
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def update_user_status(user_id: str, status: str) -> Dict:
        try:
            result = await query_db(
                f"""
                UPDATE users
                SET status = '{status}'
                WHERE id = '{user_id}'
                RETURNING *
                """
            )
            return result.get("rows", [{}])[0]
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
