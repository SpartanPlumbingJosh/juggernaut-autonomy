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


async def calculate_mrr_arr() -> Dict[str, Any]:
    """Calculate Monthly and Annual Recurring Revenue."""
    try:
        # Get recurring revenue from last 30 days
        sql = """
        SELECT 
            SUM(CASE WHEN event_type = 'recurring_revenue' THEN amount_cents ELSE 0 END) as mrr_cents,
            SUM(CASE WHEN event_type = 'recurring_revenue' THEN amount_cents ELSE 0 END) * 12 as arr_cents
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '30 days'
        """
        
        result = await query_db(sql)
        data = result.get("rows", [{}])[0]
        
        return {
            "mrr_cents": data.get("mrr_cents") or 0,
            "arr_cents": data.get("arr_cents") or 0
        }
        
    except Exception as e:
        raise Exception(f"Failed to calculate MRR/ARR: {str(e)}")


async def calculate_churn_metrics() -> Dict[str, Any]:
    """Calculate churn rate and net revenue retention."""
    try:
        # Get churned customers in last 30 days
        churn_sql = """
        SELECT COUNT(DISTINCT customer_id) as churned_customers
        FROM revenue_events
        WHERE event_type = 'churn'
          AND recorded_at >= NOW() - INTERVAL '30 days'
        """
        
        churn_result = await query_db(churn_sql)
        churned = churn_result.get("rows", [{}])[0].get("churned_customers", 0)
        
        # Get total active customers
        active_sql = """
        SELECT COUNT(DISTINCT customer_id) as active_customers
        FROM revenue_events
        WHERE event_type = 'recurring_revenue'
          AND recorded_at >= NOW() - INTERVAL '30 days'
        """
        
        active_result = await query_db(active_sql)
        active = active_result.get("rows", [{}])[0].get("active_customers", 0)
        
        # Calculate churn rate
        churn_rate = churned / active if active > 0 else 0
        
        # Calculate net revenue retention
        nrr_sql = """
        WITH recurring AS (
            SELECT customer_id, SUM(amount_cents) as total_revenue
            FROM revenue_events
            WHERE event_type = 'recurring_revenue'
              AND recorded_at >= NOW() - INTERVAL '60 days'
              AND recorded_at < NOW() - INTERVAL '30 days'
            GROUP BY customer_id
        ),
        current AS (
            SELECT customer_id, SUM(amount_cents) as total_revenue
            FROM revenue_events
            WHERE event_type = 'recurring_revenue'
              AND recorded_at >= NOW() - INTERVAL '30 days'
            GROUP BY customer_id
        )
        SELECT 
            SUM(current.total_revenue) / NULLIF(SUM(recurring.total_revenue), 0) as nrr
        FROM recurring
        LEFT JOIN current ON recurring.customer_id = current.customer_id
        """
        
        nrr_result = await query_db(nrr_sql)
        nrr = nrr_result.get("rows", [{}])[0].get("nrr", 0)
        
        return {
            "churn_rate": churn_rate,
            "net_revenue_retention": nrr
        }
        
    except Exception as e:
        raise Exception(f"Failed to calculate churn metrics: {str(e)}")


async def calculate_progress(target_cents: int = 800000000) -> Dict[str, Any]:
    """Calculate progress toward revenue target."""
    try:
        # Get total revenue to date
        sql = """
        SELECT SUM(amount_cents) as total_revenue_cents
        FROM revenue_events
        WHERE event_type = 'revenue'
        """
        
        result = await query_db(sql)
        total = result.get("rows", [{}])[0].get("total_revenue_cents", 0)
        
        progress = min(total / target_cents, 1.0)
        
        return {
            "total_revenue_cents": total,
            "target_cents": target_cents,
            "progress": progress
        }
        
    except Exception as e:
        raise Exception(f"Failed to calculate progress: {str(e)}")


async def forecast_hit_probability(target_cents: int = 800000000, deadline: str = "2026-12-31") -> Dict[str, Any]:
    """Calculate probability of hitting revenue target by deadline."""
    try:
        # Get daily revenue growth rate
        growth_sql = """
        WITH daily AS (
            SELECT 
                DATE(recorded_at) as date,
                SUM(amount_cents) as revenue_cents
            FROM revenue_events
            WHERE event_type = 'revenue'
            GROUP BY DATE(recorded_at)
        )
        SELECT 
            AVG((revenue_cents - LAG(revenue_cents) OVER (ORDER BY date)) / NULLIF(LAG(revenue_cents) OVER (ORDER BY date), 0)) as growth_rate
        FROM daily
        """
        
        growth_result = await query_db(growth_sql)
        growth_rate = growth_result.get("rows", [{}])[0].get("growth_rate", 0)
        
        # Get current revenue
        current_sql = """
        SELECT SUM(amount_cents) as total_revenue_cents
        FROM revenue_events
        WHERE event_type = 'revenue'
        """
        
        current_result = await query_db(current_sql)
        current = current_result.get("rows", [{}])[0].get("total_revenue_cents", 0)
        
        # Calculate days remaining
        deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
        days_remaining = (deadline_date - datetime.now().date()).days
        
        # Forecast future revenue
        forecast = current * (1 + growth_rate) ** days_remaining
        
        # Calculate probability
        probability = min(max(forecast / target_cents, 0), 1)
        
        return {
            "current_revenue_cents": current,
            "target_cents": target_cents,
            "days_remaining": days_remaining,
            "forecast_revenue_cents": forecast,
            "probability": probability,
            "growth_rate": growth_rate
        }
        
    except Exception as e:
        raise Exception(f"Failed to forecast hit probability: {str(e)}")


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
    
    # GET /revenue/metrics
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "metrics" and method == "GET":
        try:
            mrr_arr = await calculate_mrr_arr()
            churn_metrics = await calculate_churn_metrics()
            progress = await calculate_progress()
            forecast = await forecast_hit_probability()
            
            return _make_response(200, {
                "mrr": mrr_arr,
                "churn": churn_metrics,
                "progress": progress,
                "forecast": forecast
            })
        except Exception as e:
            return _error_response(500, str(e))
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
