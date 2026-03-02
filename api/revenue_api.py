"""
Revenue API - Expose revenue tracking data to Spartan HQ.

Endpoints:
- GET /revenue/summary - MTD/QTD/YTD totals
- GET /revenue/transactions - Transaction history 
- GET /revenue/charts - Revenue over time data
- GET /revenue/target-progress - Progress toward $14M Year 6 target
- GET /revenue/mrr - Monthly recurring revenue metrics
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


async def get_target_progress() -> Dict[str, Any]:
    """Get progress toward $14M Year 6 target."""
    try:
        # Year 6 target is $14M (14,000,000 dollars = 1,400,000,000 cents)
        TARGET_CENTS = 1_400_000_000
        
        # Get actual revenue to date
        result = await query_db("""
            SELECT EXTRACT(YEAR FROM recorded_at) as year,
                   SUM(amount_cents) as revenue_cents
            FROM revenue_events
            WHERE event_type = 'revenue'
            GROUP BY year
            ORDER BY year
        """)
        
        # Transform to percentages
        years = result.get("rows", [])
        progress = []
        cumulative_percent = 0
        cumulative_cents = 0
        
        for year_data in years:
            year = int(year_data['year'])
            cents = int(year_data['revenue_cents'] or 0)
            cumulative_cents += cents
            
            # Each year target is 1/6th of total target
            year_target_percent = (year)/6 * 100
            actual_percent = (cumulative_cents/TARGET_CENTS)*100
            
            progress.append({
                "year": year,
                "target_percent": min(year_target_percent, 100),
                "actual_percent": min(actual_percent, 100),
                "gap_percent": max(0, year_target_percent - actual_percent),
                "revenue_cents": cents,
                "cumulative_cents": cumulative_cents,
                "annual_target_cents": TARGET_CENTS/6
            })
        
        alert = None
        if progress and progress[-1]['gap_percent'] > 5:  # >5% behind target
            alert = {
                "level": "warning",
                "message": f"Currently {progress[-1]['gap_percent']:.1f}% behind target",
                "recommendation": "Consider accelerating high-ROI experiments"
            }
            
        return _make_response(200, {
            "target_cents": TARGET_CENTS,
            "years": progress,
            "alert": alert
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to calculate target progress: {str(e)}")


async def get_mrr_metrics() -> Dict[str, Any]:
    """Get monthly recurring revenue metrics."""
    try:
        # Get MRR by month
        result = await query_db("""
            SELECT 
                DATE_TRUNC('month', recorded_at) as month,
                SUM(amount_cents) as mrr_cents,
                COUNT(DISTINCT attribution->>'customer_id') as customers
            FROM revenue_events
            WHERE event_type = 'revenue'
              AND attribution->>'subscription' = 'true'
            GROUP BY month
            ORDER BY month DESC
            LIMIT 24
        """)
        
        monthly_data = result.get("rows", [])
        
        # Calculate growth rates if we have at least 2 months
        growth_rates = {}
        if len(monthly_data) >= 2:
            current = monthly_data[0]
            prev = monthly_data[1]
            mrr_growth = (current['mrr_cents'] - prev['mrr_cents'])/prev['mrr_cents']*100
            customer_growth = (current['customers'] - prev['customers'])/prev['customers']*100
            
            growth_rates = {
                "mrr_pct": mrr_growth,
                "customers_pct": customer_growth
            }
            
            # Check for negative growth
            alerts = []
            if mrr_growth < 0:
                alerts.append({
                    "level": "critical",
                    "message": f"MRR declined by {abs(mrr_growth):.1f}%",
                    "metric": "mrr"
                })
            elif mrr_growth < 5:  # Less than 5% growth
                alerts.append({
                    "level": "warning", 
                    "message": f"MRR growth slowing (+{mrr_growth:.1f}%)",
                    "metric": "mrr"
                })
                
        return _make_response(200, {
            "monthly": monthly_data,
            "growth": growth_rates,
            "alerts": alerts if 'alerts' in locals() else []
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to calculate MRR metrics: {str(e)}")


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

    # GET /revenue/target-progress
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "target-progress" and method == "GET":
        return get_target_progress()

    # GET /revenue/mrr
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "mrr" and method == "GET":
        return get_mrr_metrics()
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
