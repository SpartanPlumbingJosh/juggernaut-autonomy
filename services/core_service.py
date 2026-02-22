from typing import Dict, Optional
from fastapi import HTTPException
from core.database import query_db

class CoreService:
    @staticmethod
    async def deliver_service(user_id: str) -> Dict:
        try:
            # Check if user has active subscription
            result = await query_db(
                f"""
                SELECT * FROM subscriptions
                WHERE user_id = '{user_id}'
                AND status = 'active'
                AND (end_date IS NULL OR end_date > NOW())
                LIMIT 1
                """
            )
            if not result.get("rows"):
                raise HTTPException(status_code=403, detail="No active subscription")
            
            # Implement your core service logic here
            return {"status": "success", "message": "Service delivered"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
