"""
Revenue API - Expose revenue tracking data to Spartan HQ.

Endpoints:
- GET /revenue/summary - MTD/QTD/YTD totals
- GET /revenue/transactions - Transaction history 
- GET /revenue/charts - Revenue over time data
- GET /revenue/forecast - Revenue forecasts and projections
- GET /revenue/pipeline - Pipeline analysis and conversion rates
- GET /revenue/alerts - Revenue trajectory alerts
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


async def calculate_revenue_forecast() -> Dict[str, Any]:
    """Calculate revenue forecasts using historical trends."""
    try:
        # Get last 12 months of revenue data
        sql = """
        SELECT 
            DATE_TRUNC('month', recorded_at) as month,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '12 months'
        GROUP BY DATE_TRUNC('month', recorded_at)
        ORDER BY month DESC
        """
        
        result = await query_db(sql)
        historical = result.get("rows", [])
        
        # Simple linear forecast for next 3 months
        forecast = []
        if len(historical) >= 2:
            last_month = historical[0]
            prev_month = historical[1]
            
            # Calculate monthly growth rate
            growth_rate = (last_month["revenue_cents"] - prev_month["revenue_cents"]) / prev_month["revenue_cents"]
            
            # Project next 3 months
            for i in range(1, 4):
                projected_month = {
                    "month": (datetime.fromisoformat(last_month["month"]) + timedelta(days=30*i)).strftime("%Y-%m"),
                    "revenue_cents": last_month["revenue_cents"] * (1 + growth_rate)**i,
                    "growth_rate": growth_rate
                }
                forecast.append(projected_month)
        
        return _make_response(200, {
            "historical": historical,
            "forecast": forecast,
            "target_path": 800000000,  # $8M annual target
            "current_trajectory": sum(m["revenue_cents"] for m in historical) * (1 + growth_rate) if forecast else 0
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to calculate forecast: {str(e)}")


async def analyze_revenue_pipeline() -> Dict[str, Any]:
    """Analyze revenue pipeline conversion rates."""
    try:
        # Get pipeline stages and conversion rates
        sql = """
        SELECT 
            pipeline_stage,
            COUNT(*) as count,
            SUM(CASE WHEN converted_at IS NOT NULL THEN 1 ELSE 0 END) as converted_count,
            AVG(CASE WHEN converted_at IS NOT NULL THEN amount_cents ELSE NULL END) as avg_deal_size_cents
        FROM revenue_pipeline
        GROUP BY pipeline_stage
        ORDER BY COUNT(*) DESC
        """
        
        result = await query_db(sql)
        stages = result.get("rows", [])
        
        # Calculate conversion rates
        pipeline_analysis = []
        total_value = 0
        for stage in stages:
            conversion_rate = stage["converted_count"] / stage["count"] if stage["count"] > 0 else 0
            pipeline_analysis.append({
                "stage": stage["pipeline_stage"],
                "count": stage["count"],
                "conversion_rate": conversion_rate,
                "avg_deal_size_cents": stage["avg_deal_size_cents"],
                "projected_value_cents": stage["count"] * conversion_rate * (stage["avg_deal_size_cents"] or 0)
            })
            total_value += pipeline_analysis[-1]["projected_value_cents"]
        
        return _make_response(200, {
            "pipeline_analysis": pipeline_analysis,
            "total_projected_value_cents": total_value,
            "target_gap_cents": max(0, 800000000 - total_value)  # $8M annual target
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to analyze pipeline: {str(e)}")


async def check_revenue_alerts() -> Dict[str, Any]:
    """Check for revenue trajectory alerts."""
    try:
        # Get forecast data
        forecast_res = await calculate_revenue_forecast()
        forecast_data = json.loads(forecast_res["body"])
        
        # Get pipeline data
        pipeline_res = await analyze_revenue_pipeline()
        pipeline_data = json.loads(pipeline_res["body"])
        
        # Calculate alerts
        alerts = []
        target_path = 800000000  # $8M annual target
        
        # Forecast alert
        forecast_gap = target_path - forecast_data["current_trajectory"]
        if forecast_gap > 0:
            alerts.append({
                "type": "forecast_gap",
                "message": f"Revenue forecast is ${forecast_gap/100:.2f} below target path",
                "severity": "high" if forecast_gap > 100000000 else "medium"
            })
            
        # Pipeline alert
        pipeline_gap = pipeline_data["target_gap_cents"]
        if pipeline_gap > 0:
            alerts.append({
                "type": "pipeline_gap",
                "message": f"Pipeline value is ${pipeline_gap/100:.2f} below target",
                "severity": "high" if pipeline_gap > 100000000 else "medium"
            })
            
        return _make_response(200, {
            "alerts": alerts,
            "forecast_gap_cents": forecast_gap,
            "pipeline_gap_cents": pipeline_gap,
            "target_path_cents": target_path
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to check alerts: {str(e)}")


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
        
    # GET /revenue/forecast
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "forecast" and method == "GET":
        return await calculate_revenue_forecast()
        
    # GET /revenue/pipeline
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "pipeline" and method == "GET":
        return await analyze_revenue_pipeline()
        
    # GET /revenue/alerts
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "alerts" and method == "GET":
        return await check_revenue_alerts()
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
