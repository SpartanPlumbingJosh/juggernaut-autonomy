"""
Customer acquisition funnel tracking and optimization.
"""

from typing import Dict, List, Any
import numpy as np
import pandas as pd

class CustomerAcquisition:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql

    async def track_funnel(self, funnel_stages: List[str], time_period: str = 'day') -> Dict[str, Any]:
        """Track conversion rates through acquisition funnel stages."""
        sql = f"""
        WITH funnel_data AS (
            SELECT
                DATE_TRUNC('{time_period}', event_time) as period,
                event_name,
                COUNT(DISTINCT user_id) as users
            FROM acquisition_events
            WHERE event_name IN ({','.join(f"'{stage}'" for stage in funnel_stages)})
            GROUP BY 1, 2
        )
        SELECT
            period,
            event_name,
            users
        FROM funnel_data
        ORDER BY period, FIELD(event_name, {','.join(f"'{stage}'" for stage in funnel_stages)})
        """
        
        result = await self.execute_sql(sql)
        rows = result.get("rows", [])
        
        # Convert to pandas DataFrame for easier analysis
        df = pd.DataFrame(rows)
        pivot = df.pivot(index='period', columns='event_name', values='users')
        
        # Calculate conversion rates
        conversion_rates = {}
        for i in range(1, len(funnel_stages)):
            prev_stage = funnel_stages[i-1]
            curr_stage = funnel_stages[i]
            conversion_rates[f"{prev_stage}_to_{curr_stage}"] = pivot[curr_stage] / pivot[prev_stage]
        
        return {
            "funnel": pivot.to_dict(),
            "conversion_rates": conversion_rates.to_dict(),
            "stages": funnel_stages
        }

    async def calculate_cac(self, period: str = 'month') -> Dict[str, Any]:
        """Calculate customer acquisition cost."""
        sql = f"""
        WITH marketing_costs AS (
            SELECT
                DATE_TRUNC('{period}', event_time) as period,
                SUM(amount_cents) / 100.0 as total_cost
            FROM marketing_events
            WHERE event_type = 'cost'
            GROUP BY 1
        ),
        new_customers AS (
            SELECT
                DATE_TRUNC('{period}', MIN(recorded_at)) as period,
                COUNT(DISTINCT customer_id) as customers
            FROM revenue_events
            WHERE event_type = 'revenue'
            GROUP BY 1
        )
        SELECT
            mc.period,
            mc.total_cost,
            nc.customers,
            mc.total_cost / NULLIF(nc.customers, 0) as cac
        FROM marketing_costs mc
        JOIN new_customers nc ON mc.period = nc.period
        ORDER BY mc.period
        """
        
        result = await self.execute_sql(sql)
        rows = result.get("rows", [])
        
        return {
            "period": period,
            "data": rows
        }
