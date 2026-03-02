import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.database import query_db

class SubscriptionService:
    """Manages subscription lifecycle with support for 16M+ ARR scale."""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        
    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        payment_method_id: str,
        quantity: int = 1,
        trial_days: int = 0
    ) -> Dict[str, Any]:
        """Create and activate new subscription"""
        sub_id = str(uuid.uuid4())
        now = datetime.utcnow()
        trial_end = (now + timedelta(days=trial_days)) if trial_days else None
        
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status,
                    current_period_start, current_period_end,
                    billing_cycle_anchor, cancel_at_period_end,
                    created, start_date, trial_end,
                    quantity, metadata
                ) VALUES (
                    $1, $2, $3, 'active',
                    $4, $4 + interval '1 month',
                    $4, false,
                    $4, $4, $5,
                    $6, '{}'
                )
                """,
                sub_id, customer_id, plan_id, now,
                trial_end, quantity
            )
            
            # Record initial payment
            await self._create_invoice_item(
                conn,
                customer_id,
                plan_id,
                now,
                "setup_fee"
            )
            
        return {
            "id": sub_id,
            "status": "active",
            "current_period_start": now,
            "current_period_end": now + timedelta(days=30)
        }
        
    async def _create_invoice_item(
        self,
        conn,
        customer_id: str,
        plan_id: str,
        date: datetime,
        item_type: str
    ) -> None:
        """Record invoice item atomically"""
        item_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO invoice_items (
                id, customer_id, plan_id, 
                amount, currency, period,
                proration, item_type, date,
                metadata
            ) VALUES (
                $1, $2, $3,
                (SELECT amount FROM plans WHERE id = $3),
                'usd', daterange($4, $4 + interval '1 month', '[]'),
                false, $5, $4,
                '{}'
            )
            """,
            item_id, customer_id, plan_id,
            date, item_type
        )
