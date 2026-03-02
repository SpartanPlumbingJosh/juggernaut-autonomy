"""
Revenue Monitoring System - Track MRR, ARR, churn, growth rate and progress to $16M goal.
Includes anomaly detection and predictive forecasting.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np
from scipy.stats import zscore
from sklearn.linear_model import LinearRegression

from core.database import query_db

# Constants
ANNUAL_GOAL = 16_000_000  # $16M in cents
ANOMALY_ZSCORE_THRESHOLD = 2.5

def _calculate_mrr(revenue_cents: int) -> float:
    """Calculate Monthly Recurring Revenue."""
    return revenue_cents / 100  # Convert cents to dollars

def _calculate_arr(mrr: float) -> float:
    """Calculate Annual Recurring Revenue."""
    return mrr * 12

def _calculate_churn_rate(lost_customers: int, total_customers: int) -> float:
    """Calculate churn rate percentage."""
    if total_customers == 0:
        return 0.0
    return (lost_customers / total_customers) * 100

def _calculate_growth_rate(current: float, previous: float) -> float:
    """Calculate month-over-month growth rate percentage."""
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100

def _detect_anomalies(data: List[float]) -> List[bool]:
    """Detect anomalies using z-score method."""
    if len(data) < 2:
        return [False] * len(data)
    z_scores = zscore(data)
    return [abs(z) > ANOMALY_ZSCORE_THRESHOLD for z in z_scores]

def _forecast_revenue(data: List[float], periods: int = 6) -> List[float]:
    """Forecast future revenue using linear regression."""
    if len(data) < 2:
        return [0.0] * periods
        
    X = np.array(range(len(data))).reshape(-1, 1)
    y = np.array(data)
    model = LinearRegression()
    model.fit(X, y)
    
    future_X = np.array(range(len(data), len(data) + periods)).reshape(-1, 1)
    return model.predict(future_X).tolist()

async def get_revenue_metrics() -> Dict[str, Any]:
    """Calculate key revenue metrics."""
    try:
        # Get last 3 months of revenue data
        sql = """
        SELECT 
            DATE_TRUNC('month', recorded_at) as month,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents,
            COUNT(DISTINCT source) as active_customers,
            COUNT(DISTINCT CASE WHEN event_type = 'churn' THEN source END) as lost_customers
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '3 months'
        GROUP BY DATE_TRUNC('month', recorded_at)
        ORDER BY month DESC
        """
        
        result = await query_db(sql)
        rows = result.get("rows", [])
        
        if not rows:
            return {"error": "No revenue data found"}
            
        # Current month data
        current = rows[0]
        previous = rows[1] if len(rows) > 1 else None
        
        # Calculate metrics
        mrr = _calculate_mrr(current["revenue_cents"])
        arr = _calculate_arr(mrr)
        
        churn_rate = _calculate_churn_rate(
            current["lost_customers"],
            (previous["active_customers"] if previous else current["active_customers"])
        )
        
        growth_rate = _calculate_growth_rate(
            current["revenue_cents"],
            previous["revenue_cents"] if previous else 0
        )
        
        # Progress to $16M goal
        progress = (arr / (ANNUAL_GOAL / 100)) * 100  # Convert goal to dollars
        
        # Anomaly detection
        revenue_history = [row["revenue_cents"] for row in rows]
        anomalies = _detect_anomalies(revenue_history)
        
        # Forecasting
        forecast = _forecast_revenue(revenue_history)
        
        return {
            "mrr": round(mrr, 2),
            "arr": round(arr, 2),
            "churn_rate": round(churn_rate, 2),
            "growth_rate": round(growth_rate, 2),
            "progress_to_goal": round(progress, 2),
            "anomalies": anomalies,
            "forecast": [round(f/100, 2) for f in forecast],  # Convert cents to dollars
            "current_month": current["month"].strftime("%Y-%m"),
            "currency": "USD"
        }
        
    except Exception as e:
        return {"error": f"Failed to calculate metrics: {str(e)}"}

async def generate_weekly_report() -> Dict[str, Any]:
    """Generate weekly revenue performance report."""
    try:
        metrics = await get_revenue_metrics()
        if "error" in metrics:
            return metrics
            
        # Get weekly revenue data
        sql = """
        SELECT 
            DATE_TRUNC('week', recorded_at) as week,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '12 weeks'
        GROUP BY DATE_TRUNC('week', recorded_at)
        ORDER BY week DESC
        """
        
        result = await query_db(sql)
        weekly_data = result.get("rows", [])
        
        return {
            "metrics": metrics,
            "weekly_trend": [
                {
                    "week": row["week"].strftime("%Y-%m-%d"),
                    "revenue": round(row["revenue_cents"] / 100, 2)
                }
                for row in weekly_data
            ],
            "report_date": datetime.now().strftime("%Y-%m-%d")
        }
        
    except Exception as e:
        return {"error": f"Failed to generate report: {str(e)}"}

def route_monitoring_request(path: str, method: str, query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Route monitoring API requests."""
    
    # GET /monitoring/metrics
    if path == "/monitoring/metrics" and method == "GET":
        return get_revenue_metrics()
    
    # GET /monitoring/weekly-report
    if path == "/monitoring/weekly-report" and method == "GET":
        return generate_weekly_report()
    
    return {"error": "Not found", "status": 404}

__all__ = ["route_monitoring_request"]
```

Now let's update the revenue API to include the monitoring endpoints:

api/revenue_api.py
```python
<<<<<<< SEARCH
from core.database import query_db
