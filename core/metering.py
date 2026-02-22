import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.database import execute_sql

logger = logging.getLogger(__name__)

class UsageMeter:
    """Track and bill usage metrics."""
    
    def __init__(self):
        self.metrics = {}  # metric_name: {'unit': str, 'price_per_unit': int}
        
    def register_metric(self, metric_name: str, unit: str, price_per_unit: int) -> None:
        """Register a new usage metric."""
        self.metrics[metric_name] = {
            'unit': unit,
            'price_per_unit': price_per_unit
        }
        
    def record_usage(self, customer_id: str, metric_name: str, units: float) -> Dict[str, Any]:
        """Record usage of a metric."""
        if metric_name not in self.metrics:
            return {"success": False, "error": "Unknown metric"}
            
        try:
            execute_sql(
                f"""
                INSERT INTO usage_events (
                    id, customer_id, metric_name, units,
                    recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{metric_name}',
                    {units},
                    NOW(),
                    NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to record usage: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def generate_invoice(self, customer_id: str, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Generate invoice for usage in period."""
        try:
            # Get usage for period
            usage_sql = f"""
            SELECT metric_name, SUM(units) as total_units
            FROM usage_events
            WHERE customer_id = '{customer_id}'
              AND recorded_at >= '{period_start.isoformat()}'
              AND recorded_at < '{period_end.isoformat()}'
            GROUP BY metric_name
            """
            usage_result = execute_sql(usage_sql)
            usage_rows = usage_result.get("rows", [])
            
            # Calculate charges
            line_items = []
            total_cents = 0
            for row in usage_rows:
                metric_name = row['metric_name']
                if metric_name not in self.metrics:
                    continue
                    
                units = float(row['total_units'])
                price_per_unit = self.metrics[metric_name]['price_per_unit']
                total = int(units * price_per_unit)
                
                line_items.append({
                    'metric_name': metric_name,
                    'units': units,
                    'price_per_unit_cents': price_per_unit,
                    'total_cents': total
                })
                total_cents += total
                
            return {
                "success": True,
                "customer_id": customer_id,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "line_items": line_items,
                "total_cents": total_cents
            }
        except Exception as e:
            logger.error(f"Failed to generate invoice: {str(e)}")
            return {"success": False, "error": str(e)}
