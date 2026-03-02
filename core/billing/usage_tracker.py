from typing import Dict
from datetime import datetime
from core.database import query_db, execute_sql

class UsageTracker:
    """Tracks customer usage for metered billing."""
    
    async def record_usage(self, customer_id: str, metric: str, 
                         value: float, timestamp: datetime) -> Dict:
        """Record usage of a metered feature."""
        try:
            await execute_sql(
                f"""
                INSERT INTO usage_records (
                    id, customer_id, metric, value, recorded_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{metric}',
                    {value},
                    '{timestamp.isoformat()}'
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def get_usage(self, customer_id: str, metric: str, 
                      start: datetime, end: datetime) -> Dict:
        """Get usage for a specific metric and time period."""
        try:
            res = await query_db(
                f"""
                SELECT SUM(value) as total_usage
                FROM usage_records
                WHERE customer_id = '{customer_id}'
                  AND metric = '{metric}'
                  AND recorded_at BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'
                """
            )
            return {"success": True, "usage": res.get("rows", [{}])[0].get("total_usage", 0)}
        except Exception as e:
            return {"success": False, "error": str(e)}
