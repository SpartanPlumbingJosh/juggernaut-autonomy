"""
Enhanced revenue analytics with cohort analysis, LTV calculations, and churn metrics.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any
import numpy as np
import pandas as pd

class RevenueAnalytics:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql

    async def calculate_customer_ltv(self, customer_id: str) -> Dict[str, Any]:
        """Calculate lifetime value for a customer."""
        sql = f"""
        SELECT 
            SUM(amount_cents) / 100.0 as total_revenue,
            COUNT(*) as transaction_count,
            MIN(recorded_at) as first_purchase,
            MAX(recorded_at) as last_purchase
        FROM revenue_events
        WHERE customer_id = '{customer_id}'
          AND event_type = 'revenue'
        """
        result = await self.execute_sql(sql)
        row = result.get("rows", [{}])[0]
        
        return {
            "customer_id": customer_id,
            "total_revenue": row.get("total_revenue", 0),
            "transaction_count": row.get("transaction_count", 0),
            "first_purchase": row.get("first_purchase"),
            "last_purchase": row.get("last_purchase")
        }

    async def calculate_cohort_analysis(self, period: str = 'month') -> Dict[str, Any]:
        """Calculate cohort retention analysis."""
        sql = f"""
        WITH first_purchases AS (
            SELECT 
                customer_id,
                DATE_TRUNC('{period}', MIN(recorded_at)) as cohort_{period}
            FROM revenue_events
            WHERE event_type = 'revenue'
            GROUP BY customer_id
        ),
        activity AS (
            SELECT
                customer_id,
                DATE_TRUNC('{period}', recorded_at) as activity_{period}
            FROM revenue_events
            WHERE event_type = 'revenue'
        )
        SELECT
            fp.cohort_{period},
            a.activity_{period},
            COUNT(DISTINCT fp.customer_id) as customers
        FROM first_purchases fp
        JOIN activity a ON fp.customer_id = a.customer_id
        GROUP BY 1, 2
        ORDER BY 1, 2
        """
        
        result = await self.execute_sql(sql)
        rows = result.get("rows", [])
        
        # Convert to pandas DataFrame for easier analysis
        df = pd.DataFrame(rows)
        pivot = df.pivot(index=f'cohort_{period}', columns=f'activity_{period}', values='customers')
        
        return {
            "cohorts": pivot.to_dict(),
            "period": period
        }

    async def calculate_churn_rate(self, period: str = 'month') -> Dict[str, Any]:
        """Calculate customer churn rate."""
        sql = f"""
        WITH last_activity AS (
            SELECT
                customer_id,
                MAX(recorded_at) as last_activity
            FROM revenue_events
            WHERE event_type = 'revenue'
            GROUP BY customer_id
        )
        SELECT
            COUNT(*) FILTER (WHERE last_activity < NOW() - INTERVAL '1 {period}') as churned,
            COUNT(*) as total
        FROM last_activity
        """
        
        result = await self.execute_sql(sql)
        row = result.get("rows", [{}])[0]
        
        churn_rate = row.get("churned", 0) / row.get("total", 1) if row.get("total", 1) > 0 else 0
        
        return {
            "churn_rate": churn_rate,
            "period": period,
            "churned_customers": row.get("churned", 0),
            "total_customers": row.get("total", 0)
        }
