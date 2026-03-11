from datetime import datetime, timedelta
from typing import Dict, Optional
import uuid

class BillingService:
    """Handles payments, invoices and subscriptions"""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    async def create_subscription(self, user_id: str, plan: str, payment_method: str) -> Dict[str, Any]:
        """Create new subscription"""
        sub_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        period_end = created_at + timedelta(days=30)
        
        await self.execute_sql(f"""
            INSERT INTO subscriptions (
                id, user_id, plan, status, 
                payment_method, period_start, period_end,
                created_at, updated_at
            )
            VALUES (
                '{sub_id}', '{user_id}', '{plan}', 'active',
                '{payment_method}', '{created_at}', '{period_end}',
                '{created_at}', '{created_at}'
            )
        """)
        
        return {
            "subscription_id": sub_id,
            "user_id": user_id,
            "plan": plan,
            "period_end": period_end
        }
        
    async def create_invoice(self, user_id: str, amount: float, currency: str = "usd") -> Dict[str, Any]:
        """Create invoice for user"""
        invoice_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        
        await self.execute_sql(f"""
            INSERT INTO invoices (
                id, user_id, amount, currency,
                status, created_at, updated_at
            )
            VALUES (
                '{invoice_id}', '{user_id}', {amount}, '{currency}',
                'pending', '{created_at}', '{created_at}'
            )
        """)
        
        return {
            "invoice_id": invoice_id,
            "user_id": user_id,
            "amount": amount,
            "currency": currency,
            "status": "pending"
        }
        
    async def get_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's active subscription"""
        res = await self.execute_sql(f"""
            SELECT id, user_id, plan, status,
                   period_start, period_end, payment_method
            FROM subscriptions
            WHERE user_id = '{user_id}'
              AND status = 'active'
            ORDER BY period_end DESC
            LIMIT 1
        """)
        
        return res.get("rows", [{}])[0] if res.get("rows") else None
