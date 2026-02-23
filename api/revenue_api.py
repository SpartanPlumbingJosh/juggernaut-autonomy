"""
Revenue API - Core revenue tracking and billing system.

Endpoints:
- GET /revenue/summary - MTD/QTD/YTD totals
- GET /revenue/transactions - Transaction history
- GET /revenue/charts - Revenue over time data
- POST /revenue/subscriptions - Create new subscription
- PUT /revenue/subscriptions/{id} - Update subscription
- POST /revenue/webhooks - Handle payment provider webhooks
"""

import json
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from functools import wraps

from core.database import query_db

# Rate limiting for API endpoints
RATE_LIMITS = {
    "summary": 100,  # per minute
    "transactions": 500,  # per minute
    "subscriptions": 200,  # per minute
}

# In-memory rate limit tracking
rate_limit_counters = {k: {"count": 0, "last_reset": time.time()} for k in RATE_LIMITS}

def rate_limit(endpoint: str):
    """Decorator to enforce rate limits."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            now = time.time()
            counter = rate_limit_counters[endpoint]
            
            # Reset counter if last reset was more than 60 seconds ago
            if now - counter["last_reset"] > 60:
                counter["count"] = 0
                counter["last_reset"] = now
            
            if counter["count"] >= RATE_LIMITS[endpoint]:
                return _error_response(429, "Too many requests")
            
            counter["count"] += 1
            return f(*args, **kwargs)
        return wrapper
    return decorator


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


async def handle_create_subscription(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new subscription."""
    try:
        # Validate required fields
        required_fields = ["customer_id", "plan_id", "payment_method_id"]
        for field in required_fields:
            if not body.get(field):
                return _error_response(400, f"Missing required field: {field}")
        
        # Create subscription in database
        sql = f"""
        INSERT INTO subscriptions (
            id, customer_id, plan_id, status, 
            payment_method_id, created_at, updated_at
        ) VALUES (
            gen_random_uuid(),
            '{body["customer_id"]}',
            '{body["plan_id"]}',
            'active',
            '{body["payment_method_id"]}',
            NOW(),
            NOW()
        )
        RETURNING id
        """
        
        result = await query_db(sql)
        subscription_id = result.get("rows", [{}])[0].get("id")
        
        if not subscription_id:
            return _error_response(500, "Failed to create subscription")
        
        return _make_response(201, {"subscription_id": subscription_id})
        
    except Exception as e:
        return _error_response(500, f"Failed to create subscription: {str(e)}")


async def handle_update_subscription(subscription_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing subscription."""
    try:
        # Validate subscription exists
        check_sql = f"SELECT id FROM subscriptions WHERE id = '{subscription_id}'"
        check_result = await query_db(check_sql)
        if not check_result.get("rows"):
            return _error_response(404, "Subscription not found")
        
        # Build update query
        updates = []
        for field in ["status", "payment_method_id", "plan_id"]:
            if field in body:
                updates.append(f"{field} = '{body[field]}'")
        
        if not updates:
            return _error_response(400, "No valid fields to update")
        
        sql = f"""
        UPDATE subscriptions
        SET {", ".join(updates)}, updated_at = NOW()
        WHERE id = '{subscription_id}'
        RETURNING id
        """
        
        await query_db(sql)
        return _make_response(200, {"success": True})
        
    except Exception as e:
        return _error_response(500, f"Failed to update subscription: {str(e)}")


async def handle_webhook_event(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle payment provider webhook events."""
    try:
        event_type = body.get("type")
        data = body.get("data", {})
        
        # Handle different webhook events
        if event_type == "payment.succeeded":
            # Record successful payment
            sql = f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {data.get("amount", 0)},
                '{data.get("currency", "usd")}',
                'subscription',
                '{json.dumps(data)}'::jsonb,
                NOW(),
                NOW()
            )
            """
            await query_db(sql)
            
        elif event_type == "payment.failed":
            # Handle failed payment
            sql = f"""
            UPDATE subscriptions
            SET status = 'past_due',
                updated_at = NOW()
            WHERE payment_method_id = '{data.get("payment_method_id")}'
            """
            await query_db(sql)
            
        return _make_response(200, {"success": True})
        
    except Exception as e:
        return _error_response(500, f"Failed to process webhook: {str(e)}")


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
    
    # POST /revenue/subscriptions
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "subscriptions" and method == "POST":
        if not body:
            return _error_response(400, "Missing request body")
        return handle_create_subscription(json.loads(body))
    
    # PUT /revenue/subscriptions/{id}
    if len(parts) == 3 and parts[0] == "revenue" and parts[1] == "subscriptions" and method == "PUT":
        if not body:
            return _error_response(400, "Missing request body")
        return handle_update_subscription(parts[2], json.loads(body))
    
    # POST /revenue/webhooks
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "webhooks" and method == "POST":
        if not body:
            return _error_response(400, "Missing request body")
        return handle_webhook_event(json.loads(body))
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
