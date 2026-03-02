import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from api.revenue_api import log_revenue_event
from core.database import query_db

BASIC_PLAN_CENTS = 1000  # $10/month
PRO_PLAN_CENTS = 2900    # $29/month
ENTERPRISE_PLAN_CENTS = 9900  # $99/month

SOURCE_API = "api_subscription"


class ApiService:
    
    async def get_subscription(self, user_id: str) -> Dict[str, Any]:
        """Get user's subscription details."""
        try:
            result = await query_db(f"""
                SELECT plan, expires_at, status 
                FROM api_subscriptions
                WHERE user_id = '{user_id}'
                LIMIT 1
            """)
            return result.get("rows", [{}])[0]
        except Exception as e:
            print(f"Failed to get subscription: {str(e)}")
            return {}
    
    async def create_subscription(self, user_id: str, plan: str) -> Dict[str, Any]:
        """Create new subscription with initial payment."""
        if plan == "basic":
            amount_cents = BASIC_PLAN_CENTS
        elif plan == "pro":
            amount_cents = PRO_PLAN_CENTS
        else:
            amount_cents = ENTERPRISE_PLAN_CENTS
            
        # Log payment
        payment_id = str(uuid.uuid4())
        await log_revenue_event(
            source=SOURCE_API,
            amount_cents=amount_cents,  
            metadata={
                "user_id": user_id,
                "plan": plan,
                "payment_id": payment_id  
            }
        )
        
        # Create subscription record
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        await query_db(f"""
            INSERT INTO api_subscriptions (
                user_id,
                plan,
                billing_day,
                expires_at,
                status,
                created_at  
            ) VALUES (
                '{user_id}',
                '{plan}',
                {datetime.now(timezone.utc).day},
                '{expires.isoformat()}',
                'active',
                NOW()
            )
            ON CONFLICT (user_id) 
            DO UPDATE SET
                plan = EXCLUDED.plan,
                expires_at = EXCLUDED.expires_at,
                status = EXCLUDED.status
        """)
        
        return {"success": True, "payment_id": payment_id}
