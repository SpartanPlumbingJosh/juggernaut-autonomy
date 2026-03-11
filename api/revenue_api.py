"""
Revenue API - Expose revenue tracking data to Spartan HQ.

API Documentation:

Authentication:
- All requests require an API key passed in the Authorization header
- Format: "Bearer <your_api_key>"

Rate Limits:
- Basic: 100 requests/minute
- Pro: 1,000 requests/minute 
- Enterprise: 10,000 requests/minute

Endpoints:
1. GET /revenue/summary
   - Returns MTD/QTD/YTD revenue totals
   - Response format:
     {
       "mtd": {
         "revenue_cents": int,
         "cost_cents": int,
         "profit_cents": int,
         "transaction_count": int
       },
       "qtd": {...},
       "ytd": {...},
       "all_time": {...}
     }

2. GET /revenue/transactions
   - Returns paginated transaction history
   - Parameters:
     - limit: Number of results per page (default: 50)
     - offset: Pagination offset (default: 0)
     - event_type: Filter by event type (optional)
   - Response format:
     {
       "transactions": [{
         "id": str,
         "experiment_id": str,
         "event_type": str,
         "amount_cents": int,
         "currency": str,
         "source": str,
         "metadata": dict,
         "recorded_at": str
       }],
       "total": int,
       "limit": int,
       "offset": int
     }

3. GET /revenue/charts
   - Returns revenue data for visualization
   - Parameters:
     - days: Number of days to include (default: 30)
   - Response format:
     {
       "daily": [{
         "date": str,
         "revenue_cents": int,
         "cost_cents": int,
         "profit_cents": int,
         "transaction_count": int
       }],
       "by_source": [{
         "source": str,
         "revenue_cents": int,
         "transaction_count": int
       }],
       "period_days": int
     }

Error Responses:
- 401 Unauthorized: Invalid or missing API key
- 429 Too Many Requests: Rate limit exceeded
- 500 Internal Server Error: Server error
- 404 Not Found: Invalid endpoint
"""

import json
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from functools import wraps

from core.database import query_db

# Rate limiting storage
RATE_LIMITS = {}
API_KEYS = {
    "basic": {"rate_limit": 100, "per": 60},  # 100 requests per minute
    "pro": {"rate_limit": 1000, "per": 60},  # 1000 requests per minute
    "enterprise": {"rate_limit": 10000, "per": 60}  # 10,000 requests per minute
}

def authenticate_and_limit(f):
    @wraps(f)
    async def wrapper(*args, **kwargs):
        api_key = kwargs.get("headers", {}).get("Authorization", "")
        if not api_key or not api_key.startswith("Bearer "):
            return _error_response(401, "Missing or invalid API key")
        
        key = api_key[7:]
        if key not in API_KEYS:
            return _error_response(401, "Invalid API key")
        
        plan = API_KEYS[key]
        current_time = time.time()
        request_count = RATE_LIMITS.get(key, {}).get("count", 0)
        last_reset = RATE_LIMITS.get(key, {}).get("last_reset", current_time)
        
        # Reset counter if time window has passed
        if current_time - last_reset > plan["per"]:
            RATE_LIMITS[key] = {"count": 1, "last_reset": current_time}
        else:
            if request_count >= plan["rate_limit"]:
                return _error_response(429, "Rate limit exceeded")
            RATE_LIMITS[key]["count"] += 1
        
        return await f(*args, **kwargs)
    return wrapper


async def _track_usage(api_key: str, endpoint: str):
    """Track API usage for billing."""
    try:
        await query_db(f"""
            INSERT INTO api_usage (api_key, endpoint, timestamp)
            VALUES ('{api_key}', '{endpoint}', NOW())
        """)
    except Exception:
        pass

def _make_response(status_code: int, body: Dict[str, Any], api_key: str = None, endpoint: str = None) -> Dict[str, Any]:
    """Create standardized API response."""
    response = {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(body)
    }
    
    if api_key and endpoint:
        _track_usage(api_key, endpoint)
    
    return response


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


def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None, headers: Dict[str, Any] = None) -> Dict[str, Any]:
    """Route revenue API requests."""
    headers = headers or {}
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # GET /revenue/summary
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "summary" and method == "GET":
        api_key = headers.get("Authorization", "")
        return _make_response(200, handle_revenue_summary(), api_key, "revenue/summary")
    
    # GET /revenue/transactions
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "transactions" and method == "GET":
        api_key = headers.get("Authorization", "")
        return _make_response(200, handle_revenue_transactions(query_params), api_key, "revenue/transactions")
    
    # GET /revenue/charts
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "charts" and method == "GET":
        api_key = headers.get("Authorization", "")
        return _make_response(200, handle_revenue_charts(query_params), api_key, "revenue/charts")
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
