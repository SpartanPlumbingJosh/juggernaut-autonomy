"""
Revenue API - Expose revenue tracking data to Spartan HQ.

Endpoints:
- GET /revenue/summary - MTD/QTD/YTD totals
- GET /revenue/transactions - Transaction history
- GET /revenue/charts - Revenue over time data
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.database import query_db


def _make_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(body)
    }


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create error response."""
    return _make_response(status_code, {"error": message})


async def handle_revenue_summary() -> Dict[str, Any]:
    """Get MTD/QTD/YTD revenue totals."""
    try:
        now = datetime.now(timezone.utc)
        
        # Calculate period boundaries
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        quarter_month = ((now.month - 1) // 3) * 3 + 1
        quarter_start = now.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get revenue by period
        sql = f"""
        SELECT 
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as total_revenue_cents,
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as total_cost_cents,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) - 
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as net_profit_cents,
            COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count,
            MIN(recorded_at) FILTER (WHERE event_type = 'revenue') as first_revenue_at,
            MAX(recorded_at) FILTER (WHERE event_type = 'revenue') as last_revenue_at
        FROM revenue_events
        WHERE recorded_at >= '{month_start.isoformat()}'
        """
        
        mtd_result = await query_db(sql.replace(month_start.isoformat(), month_start.isoformat()))
        mtd = mtd_result.get("rows", [{}])[0]
        
        qtd_result = await query_db(sql.replace(month_start.isoformat(), quarter_start.isoformat()))
        qtd = qtd_result.get("rows", [{}])[0]
        
        ytd_result = await query_db(sql.replace(month_start.isoformat(), year_start.isoformat()))
        ytd = ytd_result.get("rows", [{}])[0]
        
        # All-time totals
        all_time_sql = """
        SELECT 
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as total_revenue_cents,
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as total_cost_cents,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) - 
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as net_profit_cents,
            COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count
        FROM revenue_events
        """
        
        all_time_result = await query_db(all_time_sql)
        all_time = all_time_result.get("rows", [{}])[0]
        
        return _make_response(200, {
            "mtd": {
                "revenue_cents": mtd.get("total_revenue_cents") or 0,
                "cost_cents": mtd.get("total_cost_cents") or 0,
                "profit_cents": mtd.get("net_profit_cents") or 0,
                "transaction_count": mtd.get("transaction_count") or 0,
                "first_revenue_at": mtd.get("first_revenue_at"),
                "last_revenue_at": mtd.get("last_revenue_at")
            },
            "qtd": {
                "revenue_cents": qtd.get("total_revenue_cents") or 0,
                "cost_cents": qtd.get("total_cost_cents") or 0,
                "profit_cents": qtd.get("net_profit_cents") or 0,
                "transaction_count": qtd.get("transaction_count") or 0
            },
            "ytd": {
                "revenue_cents": ytd.get("total_revenue_cents") or 0,
                "cost_cents": ytd.get("total_cost_cents") or 0,
                "profit_cents": ytd.get("net_profit_cents") or 0,
                "transaction_count": ytd.get("transaction_count") or 0
            },
            "all_time": {
                "revenue_cents": all_time.get("total_revenue_cents") or 0,
                "cost_cents": all_time.get("total_cost_cents") or 0,
                "profit_cents": all_time.get("net_profit_cents") or 0,
                "transaction_count": all_time.get("transaction_count") or 0
            }
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch revenue summary: {str(e)}")


async def handle_revenue_transactions(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Get transaction history with pagination."""
    try:
        limit = int(query_params.get("limit", ["50"])[0] if isinstance(query_params.get("limit"), list) else query_params.get("limit", 50))
        offset = int(query_params.get("offset", ["0"])[0] if isinstance(query_params.get("offset"), list) else query_params.get("offset", 0))
        event_type = query_params.get("event_type", [""])[0] if isinstance(query_params.get("event_type"), list) else query_params.get("event_type", "")
        
        where_clause = ""
        if event_type:
            where_clause = f"WHERE event_type = '{event_type}'"
        
        sql = f"""
        SELECT 
            id,
            experiment_id,
            event_type,
            amount_cents,
            currency,
            source,
            metadata,
            recorded_at,
            created_at
        FROM revenue_events
        {where_clause}
        ORDER BY recorded_at DESC
        LIMIT {limit}
        OFFSET {offset}
        """
        
        result = await query_db(sql)
        transactions = result.get("rows", [])
        
        # Get total count
        count_sql = f"SELECT COUNT(*) as total FROM revenue_events {where_clause}"
        count_result = await query_db(count_sql)
        total = count_result.get("rows", [{}])[0].get("total", 0)
        
        return _make_response(200, {
            "transactions": transactions,
            "total": total,
            "limit": limit,
            "offset": offset
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch transactions: {str(e)}")


async def handle_revenue_charts(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Get revenue over time for charts."""
    try:
        days = int(query_params.get("days", ["30"])[0] if isinstance(query_params.get("days"), list) else query_params.get("days", 30))
        
        # Daily revenue for the last N days
        sql = f"""
        SELECT 
            DATE(recorded_at) as date,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents,
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as cost_cents,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) - 
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as profit_cents,
            COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '{days} days'
        GROUP BY DATE(recorded_at)
        ORDER BY date DESC
        """
        
        result = await query_db(sql)
        daily_data = result.get("rows", [])
        
        # By source
        source_sql = f"""
        SELECT 
            source,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents,
            COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '{days} days'
        GROUP BY source
        ORDER BY revenue_cents DESC
        """
        
        source_result = await query_db(source_sql)
        by_source = source_result.get("rows", [])
        
        return _make_response(200, {
            "daily": daily_data,
            "by_source": by_source,
            "period_days": days
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch chart data: {str(e)}")


def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route revenue API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # GET /revenue/summary
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "summary" and method == "GET":
        return handle_revenue_summary()
    
    # GET /revenue/transactions
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "transactions" and method == "GET":
        return handle_revenue_transactions(query_params)
    
    # GET /revenue/charts
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "charts" and method == "GET":
        return handle_revenue_charts(query_params)
    
    # GET /revenue/monitor
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "monitor" and method == "GET":
        from api.revenue_monitor import get_revenue_dashboard
        dashboard = await get_revenue_dashboard()
        return _make_response(200, dashboard)
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
"""
Automated Revenue Monitoring System

Features:
- Real-time MRR/ARR calculation
- Customer cohort tracking
- Revenue trajectory projection
- Alerting for revenue shortfalls
- Dashboard APIs for metrics visualization
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import math

from core.database import query_db

# Constants
TARGET_REVENUE = 8_000_000  # $8M annual target
ALERT_THRESHOLD = 0.9  # 90% of target

async def calculate_mrr_arr() -> Dict[str, float]:
    """Calculate Monthly and Annual Recurring Revenue."""
    try:
        # Get recurring revenue from last 30 days
        sql = """
        SELECT SUM(amount_cents)/100 as revenue
        FROM revenue_events
        WHERE event_type = 'revenue'
          AND recorded_at >= NOW() - INTERVAL '30 days'
          AND metadata->>'recurring' = 'true'
        """
        result = await query_db(sql)
        mrr = float(result.get("rows", [{}])[0].get("revenue", 0))
        arr = mrr * 12
        return {"mrr": mrr, "arr": arr}
    except Exception as e:
        return {"error": str(e)}

async def track_customer_cohorts() -> Dict[str, Dict]:
    """Track customer cohorts by acquisition month."""
    try:
        sql = """
        SELECT 
            DATE_TRUNC('month', recorded_at) as cohort_month,
            COUNT(DISTINCT metadata->>'customer_id') as customers,
            SUM(amount_cents)/100 as revenue
        FROM revenue_events
        WHERE event_type = 'revenue'
        GROUP BY cohort_month
        ORDER BY cohort_month DESC
        """
        result = await query_db(sql)
        cohorts = {}
        for row in result.get("rows", []):
            month = row["cohort_month"].strftime("%Y-%m")
            cohorts[month] = {
                "customers": row["customers"],
                "revenue": row["revenue"]
            }
        return cohorts
    except Exception as e:
        return {"error": str(e)}

async def project_revenue_trajectory() -> Dict[str, Any]:
    """Project revenue trajectory toward $8M target."""
    try:
        # Get current ARR
        arr_data = await calculate_mrr_arr()
        current_arr = arr_data.get("arr", 0)
        
        # Get growth rate from last 3 months
        sql = """
        SELECT 
            SUM(amount_cents)/100 as revenue
        FROM revenue_events
        WHERE event_type = 'revenue'
          AND recorded_at >= NOW() - INTERVAL '3 months'
        """
        result = await query_db(sql)
        three_month_revenue = float(result.get("rows", [{}])[0].get("revenue", 0))
        monthly_growth = three_month_revenue / 3
        
        # Project trajectory
        months_needed = math.ceil((TARGET_REVENUE - current_arr) / monthly_growth)
        projection_date = (datetime.now() + timedelta(days=months_needed*30)).strftime("%Y-%m-%d")
        
        return {
            "current_arr": current_arr,
            "monthly_growth": monthly_growth,
            "months_needed": months_needed,
            "projection_date": projection_date,
            "target_revenue": TARGET_REVENUE
        }
    except Exception as e:
        return {"error": str(e)}

async def check_revenue_alerts() -> Dict[str, Any]:
    """Check for revenue shortfall alerts."""
    try:
        arr_data = await calculate_mrr_arr()
        current_arr = arr_data.get("arr", 0)
        
        if current_arr < TARGET_REVENUE * ALERT_THRESHOLD:
            return {
                "alert": True,
                "message": f"Revenue shortfall: Current ARR ${current_arr:,.0f} is below {ALERT_THRESHOLD*100}% of target",
                "current_arr": current_arr,
                "target": TARGET_REVENUE
            }
        return {"alert": False}
    except Exception as e:
        return {"error": str(e)}

async def get_revenue_dashboard() -> Dict[str, Any]:
    """Get all revenue metrics for dashboard."""
    try:
        mrr_arr = await calculate_mrr_arr()
        cohorts = await track_customer_cohorts()
        trajectory = await project_revenue_trajectory()
        alerts = await check_revenue_alerts()
        
        return {
            "mrr": mrr_arr.get("mrr"),
            "arr": mrr_arr.get("arr"),
            "cohorts": cohorts,
            "trajectory": trajectory,
            "alerts": alerts
        }
    except Exception as e:
        return {"error": str(e)}
