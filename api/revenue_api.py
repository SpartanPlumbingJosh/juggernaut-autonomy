"""
Revenue API - Expose revenue tracking data to Spartan HQ.

Endpoints:
- GET /revenue/summary - MTD/QTD/YTD totals
- GET /revenue/transactions - Transaction history 
- GET /revenue/charts - Revenue over time data
- GET /revenue/dashboard - Real-time dashboard metrics
- GET /revenue/forecast - Revenue projections and milestones
"""

import json
from datetime import datetime, timezone, timedelta
import numpy as np
from scipy.stats import linregress
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


async def _get_revenue_trend(days: int = 90) -> Dict[str, Any]:
    """Calculate revenue trend and growth metrics."""
    sql = f"""
    SELECT 
        DATE(recorded_at) as date,
        SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents
    FROM revenue_events
    WHERE recorded_at >= NOW() - INTERVAL '{days} days'
    GROUP BY DATE(recorded_at)
    ORDER BY date ASC
    """
    
    result = await query_db(sql)
    daily_data = result.get("rows", [])
    
    if not daily_data:
        return {}
    
    # Convert to numpy arrays for analysis
    dates = [datetime.strptime(d['date'], '%Y-%m-%d') for d in daily_data]
    revenues = np.array([d['revenue_cents'] / 100 for d in daily_data])  # Convert to dollars
    
    # Linear regression for trend
    x = np.array([(d - dates[0]).days for d in dates])
    slope, intercept, r_value, p_value, std_err = linregress(x, revenues)
    
    # Calculate growth metrics
    weekly_growth = (revenues[-7:].sum() - revenues[-14:-7].sum()) / revenues[-14:-7].sum() if len(revenues) >= 14 else 0
    monthly_growth = (revenues[-30:].sum() - revenues[-60:-30].sum()) / revenues[-60:-30].sum() if len(revenues) >= 60 else 0
    
    return {
        "daily": daily_data,
        "trend": {
            "slope": slope,
            "intercept": intercept,
            "r_squared": r_value**2,
            "std_err": std_err
        },
        "growth": {
            "weekly": weekly_growth,
            "monthly": monthly_growth
        }
    }

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
    
    # GET /revenue/dashboard
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "dashboard" and method == "GET":
        return await handle_revenue_dashboard()
    
    # GET /revenue/forecast
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "forecast" and method == "GET":
        return await handle_revenue_forecast()
    
    return _error_response(404, "Not found")

async def handle_revenue_dashboard() -> Dict[str, Any]:
    """Get real-time dashboard metrics."""
    try:
        # Get current revenue totals
        now = datetime.now(timezone.utc)
        year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        ytd_sql = f"""
        SELECT 
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as total_revenue_cents
        FROM revenue_events
        WHERE recorded_at >= '{year_start.isoformat()}'
        """
        ytd_result = await query_db(ytd_sql)
        ytd_revenue = ytd_result.get("rows", [{}])[0].get("total_revenue_cents", 0) / 100
        
        # Get trend data
        trend_data = await _get_revenue_trend()
        
        # Calculate progress toward $14M target
        target = 14_000_000
        progress = ytd_revenue / target
        projected = trend_data.get("trend", {}).get("slope", 0) * 365
        
        return _make_response(200, {
            "ytd_revenue": ytd_revenue,
            "target": target,
            "progress": progress,
            "projected_annual": projected,
            "trend": trend_data.get("trend", {}),
            "growth": trend_data.get("growth", {})
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch dashboard data: {str(e)}")

async def handle_revenue_forecast() -> Dict[str, Any]:
    """Get revenue projections and milestone tracking."""
    try:
        # Get historical data
        trend_data = await _get_revenue_trend(365)
        daily_data = trend_data.get("daily", [])
        
        if not daily_data:
            return _make_response(200, {"forecast": [], "milestones": []})
        
        # Convert to numpy arrays
        dates = [datetime.strptime(d['date'], '%Y-%m-%d') for d in daily_data]
        revenues = np.array([d['revenue_cents'] / 100 for d in daily_data])
        
        # Forecast using linear regression
        x = np.array([(d - dates[0]).days for d in dates])
        slope, intercept, _, _, _ = linregress(x, revenues)
        
        # Generate 12 month forecast
        forecast = []
        for i in range(1, 13):
            future_date = dates[-1] + timedelta(days=30*i)
            projected = slope * (x[-1] + 30*i) + intercept
            forecast.append({
                "date": future_date.strftime('%Y-%m-%d'),
                "projected_revenue": max(0, projected)
            })
        
        # Calculate milestones
        target = 14_000_000
        current = revenues[-1]
        projected_end = forecast[-1]['projected_revenue']
        gap = target - projected_end
        
        milestones = [
            {"name": "Q1 Target", "target": target * 0.25, "current": current},
            {"name": "H1 Target", "target": target * 0.5, "current": current},
            {"name": "Q3 Target", "target": target * 0.75, "current": current},
            {"name": "Annual Target", "target": target, "current": current}
        ]
        
        return _make_response(200, {
            "forecast": forecast,
            "milestones": milestones,
            "gap_to_target": gap,
            "trend": trend_data.get("trend", {})
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to generate forecast: {str(e)}")


__all__ = ["route_request"]
