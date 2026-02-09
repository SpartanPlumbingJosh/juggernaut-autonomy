"""
Revenue Tracker - Records and manages all revenue-related events.
"""
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

class RevenueTracker:
    def __init__(self, db_executor):
        self.db_executor = db_executor

    async def record_revenue_event(
        self,
        event_type: str,
        amount_cents: int,
        currency: str,
        source: str,
        metadata: Optional[Dict] = None,
        recorded_at: Optional[str] = None,
        attribution: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Record a revenue or cost event."""
        try:
            recorded_time = recorded_at or datetime.utcnow().isoformat()
            
            sql = """
            INSERT INTO revenue_events (
                id,
                event_type,
                amount_cents,
                currency,
                source,
                metadata,
                recorded_at,
                attribution,
                created_at
            ) VALUES (
                gen_random_uuid(),
                %(event_type)s,
                %(amount_cents)s,
                %(currency)s,
                %(source)s,
                %(metadata)s,
                %(recorded_at)s,
                %(attribution)s,
                NOW()
            )
            RETURNING id
            """
            
            params = {
                "event_type": event_type,
                "amount_cents": amount_cents,
                "currency": currency,
                "source": source,
                "metadata": metadata or {},
                "recorded_at": recorded_time,
                "attribution": attribution or {}
            }
            
            result = await self.db_executor(sql, params)
            return {"success": True, "event_id": result.get("rows", [{}])[0].get("id")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_customer_lifetime_value(self, customer_id: str) -> Dict[str, Any]:
        """Calculate lifetime value for a customer."""
        try:
            sql = """
            SELECT 
                SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as total_revenue,
                SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as total_cost,
                COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count
            FROM revenue_events
            WHERE attribution->>'customer_id' = %(customer_id)s
            """
            
            result = await self.db_executor(sql, {"customer_id": customer_id})
            row = result.get("rows", [{}])[0]
            
            return {
                "success": True,
                "revenue_cents": row.get("total_revenue", 0),
                "cost_cents": row.get("total_cost", 0),
                "transaction_count": row.get("transaction_count", 0),
                "net_value": row.get("total_revenue", 0) - row.get("total_cost", 0)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_product_revenue(self, product_id: str) -> Dict[str, Any]:
        """Calculate revenue metrics for a specific product."""
        try:
            sql = """
            SELECT 
                SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as total_revenue,
                SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as total_cost,
                COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count,
                MIN(recorded_at) as first_transaction,
                MAX(recorded_at) as last_transaction
            FROM revenue_events
            WHERE attribution->>'product_id' = %(product_id)s
            """
            
            result = await self.db_executor(sql, {"product_id": product_id})
            row = result.get("rows", [{}])[0]
            
            return {
                "success": True,
                "revenue_cents": row.get("total_revenue", 0),
                "cost_cents": row.get("total_cost", 0),
                "transaction_count": row.get("transaction_count", 0),
                "first_transaction": row.get("first_transaction"),
                "last_transaction": row.get("last_transaction")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
