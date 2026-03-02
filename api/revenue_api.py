"""
Revenue Tracking System - Automated revenue tracking with forecasting and milestone alerts.

Endpoints:
- GET /revenue/summary - MTD/QTD/YTD totals vs $16M target
- GET /revenue/transactions - Transaction history
- GET /revenue/charts - Revenue over time data
- POST /revenue/transactions - Ingest new revenue transactions
- GET /revenue/forecast - Revenue forecast and projections
- GET /revenue/milestones - Critical path milestone tracking
"""

import json
from datetime import datetime, timezone, timedelta
import numpy as np
from scipy.optimize import curve_fit
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


# Constants
TARGET_REVENUE = 16_000_000 * 100  # $16M target in cents

def _calculate_progress(current: int, target: int) -> Dict[str, Any]:
    """Calculate progress metrics."""
    percent = (current / target) * 100 if target > 0 else 0
    remaining = max(target - current, 0)
    return {
        "current": current,
        "target": target,
        "percent": round(percent, 1),
        "remaining": remaining
    }

async def handle_revenue_summary() -> Dict[str, Any]:
    """Get MTD/QTD/YTD revenue totals vs $16M target."""
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
        
        # Calculate progress vs target
        ytd_revenue = ytd.get("total_revenue_cents") or 0
        progress = _calculate_progress(ytd_revenue, TARGET_REVENUE)

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
            },
            "target_progress": progress
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


async def ingest_revenue_transaction(body: Dict[str, Any]) -> Dict[str, Any]:
    """Ingest new revenue transaction."""
    try:
        required_fields = ["amount_cents", "currency", "source", "event_type", "recorded_at"]
        if not all(field in body for field in required_fields):
            return _error_response(400, "Missing required fields")
        
        # Validate amount
        try:
            amount = int(body["amount_cents"])
            if amount <= 0:
                return _error_response(400, "Amount must be positive")
        except ValueError:
            return _error_response(400, "Invalid amount")
        
        # Insert transaction
        sql = f"""
        INSERT INTO revenue_events (
            id, amount_cents, currency, source, event_type, 
            recorded_at, created_at, metadata
        ) VALUES (
            gen_random_uuid(),
            {amount},
            '{body["currency"]}',
            '{body["source"]}',
            '{body["event_type"]}',
            '{body["recorded_at"]}',
            NOW(),
            '{json.dumps(body.get("metadata", {}))}'
        )
        """
        await query_db(sql)
        return _make_response(200, {"success": True})
    except Exception as e:
        return _error_response(500, f"Failed to ingest transaction: {str(e)}")

def _forecast_revenue(daily_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Forecast revenue using exponential growth model."""
    if not daily_data:
        return {}
    
    # Prepare data
    dates = [datetime.fromisoformat(d["date"]) for d in daily_data]
    revenues = [d["revenue_cents"] for d in daily_data]
    days_since_start = [(d - dates[0]).days for d in dates]
    
    # Exponential growth model
    def model(x, a, b):
        return a * np.exp(b * x)
    
    try:
        # Fit model
        popt, _ = curve_fit(model, days_since_start, revenues, p0=[1, 0.01])
        
        # Forecast next 30 days
        forecast_days = days_since_start[-1] + np.arange(1, 31)
        forecast_revenues = model(forecast_days, *popt)
        
        # Calculate projected total
        projected_total = sum(revenues) + sum(forecast_revenues)
        progress = _calculate_progress(projected_total, TARGET_REVENUE)
        
        return {
            "forecast_dates": [(dates[0] + timedelta(days=int(d))).isoformat() for d in forecast_days],
            "forecast_revenues": [int(r) for r in forecast_revenues],
            "projected_total": int(projected_total),
            "target_progress": progress
        }
    except Exception:
        return {}

async def handle_revenue_forecast() -> Dict[str, Any]:
    """Get revenue forecast and projections."""
    try:
        # Get last 90 days of daily revenue
        sql = """
        SELECT 
            DATE(recorded_at) as date,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '90 days'
        GROUP BY DATE(recorded_at)
        ORDER BY date ASC
        """
        result = await query_db(sql)
        daily_data = result.get("rows", [])
        
        forecast = _forecast_revenue(daily_data)
        return _make_response(200, {"forecast": forecast})
    except Exception as e:
        return _error_response(500, f"Failed to generate forecast: {str(e)}")

async def handle_revenue_milestones() -> Dict[str, Any]:
    """Get critical path milestone tracking."""
    try:
        # Calculate milestones based on target
        sql = """
        SELECT 
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as total_revenue_cents
        FROM revenue_events
        """
        result = await query_db(sql)
        total_revenue = result.get("rows", [{}])[0].get("total_revenue_cents", 0)
        
        milestones = [
            {"name": "25%", "target": TARGET_REVENUE * 0.25, "achieved": total_revenue >= TARGET_REVENUE * 0.25},
            {"name": "50%", "target": TARGET_REVENUE * 0.5, "achieved": total_revenue >= TARGET_REVENUE * 0.5},
            {"name": "75%", "target": TARGET_REVENUE * 0.75, "achieved": total_revenue >= TARGET_REVENUE * 0.75},
            {"name": "100%", "target": TARGET_REVENUE, "achieved": total_revenue >= TARGET_REVENUE},
        ]
        
        return _make_response(200, {"milestones": milestones})
    except Exception as e:
        return _error_response(500, f"Failed to get milestones: {str(e)}")

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
    
    # POST /revenue/transactions
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "transactions" and method == "POST":
        return await ingest_revenue_transaction(json.loads(body or "{}"))
    
    # GET /revenue/forecast
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "forecast" and method == "GET":
        return await handle_revenue_forecast()
    
    # GET /revenue/milestones
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "milestones" and method == "GET":
        return await handle_revenue_milestones()
    
    # GET /revenue/charts
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "charts" and method == "GET":
        return await handle_revenue_charts(query_params)
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
