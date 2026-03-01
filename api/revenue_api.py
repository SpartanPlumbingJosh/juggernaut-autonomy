"""
Revenue API - Expose revenue tracking data to Spartan HQ.

Endpoints:
- GET /revenue/summary - MTD/QTD/YTD totals
- GET /revenue/transactions - Transaction history
- GET /revenue/charts - Revenue over time data
- POST /revenue/subscriptions - Create new subscription
- GET /revenue/subscriptions/{id} - Get subscription details
- POST /revenue/subscriptions/{id}/cancel - Cancel subscription
- POST /revenue/subscriptions/{id}/charge - Process payment
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


async def create_subscription(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create new subscription."""
    try:
        # Validate required fields
        required_fields = ["customer_id", "plan_id", "payment_method"]
        for field in required_fields:
            if field not in body:
                return _error_response(400, f"Missing required field: {field}")

        # Basic fraud check - limit subscriptions per customer
        sql = f"""
        SELECT COUNT(*) as count
        FROM subscriptions
        WHERE customer_id = '{body["customer_id"]}'
          AND status = 'active'
        """
        result = await query_db(sql)
        if result.get("rows", [{}])[0].get("count", 0) >= 3:
            return _error_response(400, "Maximum active subscriptions reached")

        # Create subscription
        subscription_id = str(uuid.uuid4())
        sql = f"""
        INSERT INTO subscriptions (
            id, customer_id, plan_id, payment_method,
            status, created_at, updated_at
        ) VALUES (
            '{subscription_id}',
            '{body["customer_id"]}',
            '{body["plan_id"]}',
            '{body["payment_method"]}',
            'active',
            NOW(),
            NOW()
        )
        """
        await query_db(sql)

        return _make_response(200, {
            "subscription_id": subscription_id,
            "status": "active"
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to create subscription: {str(e)}")


async def get_subscription(subscription_id: str) -> Dict[str, Any]:
    """Get subscription details."""
    try:
        sql = f"""
        SELECT *
        FROM subscriptions
        WHERE id = '{subscription_id}'
        """
        result = await query_db(sql)
        subscription = result.get("rows", [{}])[0]
        
        if not subscription.get("id"):
            return _error_response(404, "Subscription not found")
            
        return _make_response(200, subscription)
        
    except Exception as e:
        return _error_response(500, f"Failed to get subscription: {str(e)}")


async def cancel_subscription(subscription_id: str) -> Dict[str, Any]:
    """Cancel subscription."""
    try:
        sql = f"""
        UPDATE subscriptions
        SET status = 'canceled',
            updated_at = NOW()
        WHERE id = '{subscription_id}'
        """
        await query_db(sql)
        
        return _make_response(200, {"status": "canceled"})
        
    except Exception as e:
        return _error_response(500, f"Failed to cancel subscription: {str(e)}")


async def process_payment(subscription_id: str) -> Dict[str, Any]:
    """Process subscription payment."""
    try:
        # Get subscription details
        subscription = await get_subscription(subscription_id)
        if subscription["statusCode"] != 200:
            return subscription
            
        # Get plan details
        sql = f"""
        SELECT *
        FROM plans
        WHERE id = '{subscription["body"]["plan_id"]}'
        """
        result = await query_db(sql)
        plan = result.get("rows", [{}])[0]
        
        if not plan.get("id"):
            return _error_response(404, "Plan not found")
            
        # Process payment (mock implementation)
        payment_id = str(uuid.uuid4())
        sql = f"""
        INSERT INTO payments (
            id, subscription_id, amount_cents,
            currency, status, created_at
        ) VALUES (
            '{payment_id}',
            '{subscription_id}',
            {plan["amount_cents"]},
            '{plan["currency"]}',
            'pending',
            NOW()
        )
        """
        await query_db(sql)
        
        # Simulate payment processing
        await asyncio.sleep(1)
        
        # Update payment status
        sql = f"""
        UPDATE payments
        SET status = 'completed',
            updated_at = NOW()
        WHERE id = '{payment_id}'
        """
        await query_db(sql)
        
        return _make_response(200, {
            "payment_id": payment_id,
            "status": "completed",
            "amount_cents": plan["amount_cents"],
            "currency": plan["currency"]
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to process payment: {str(e)}")


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
    
    # Subscription endpoints
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "subscriptions" and method == "POST":
        try:
            body_data = json.loads(body) if body else {}
            return create_subscription(body_data)
        except json.JSONDecodeError:
            return _error_response(400, "Invalid JSON body")
    
    if len(parts) == 3 and parts[0] == "revenue" and parts[1] == "subscriptions" and method == "GET":
        return get_subscription(parts[2])
    
    if len(parts) == 4 and parts[0] == "revenue" and parts[1] == "subscriptions" and parts[2] and parts[3] == "cancel" and method == "POST":
        return cancel_subscription(parts[2])
    
    if len(parts) == 4 and parts[0] == "revenue" and parts[1] == "subscriptions" and parts[2] and parts[3] == "charge" and method == "POST":
        return process_payment(parts[2])
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
