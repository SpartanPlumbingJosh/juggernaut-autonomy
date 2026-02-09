"""
Revenue API - Expose revenue tracking data to Spartan HQ.

Endpoints:
- GET /revenue/summary - MTD/QTD/YTD totals
- GET /revenue/transactions - Transaction history 
- GET /revenue/charts - Revenue over time data
- POST /revenue/subscriptions - Create new subscription
- POST /revenue/payments - Process payment
- POST /revenue/webhooks - Handle payment webhooks
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
            
        return _make_response(201, {
            "subscription_id": subscription_id,
            "status": "active"
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to create subscription: {str(e)}")


async def handle_process_payment(body: Dict[str, Any]) -> Dict[str, Any]:
    """Process a payment."""
    try:
        # Validate required fields
        required_fields = ["subscription_id", "amount_cents", "currency"]
        for field in required_fields:
            if not body.get(field):
                return _error_response(400, f"Missing required field: {field}")
        
        # Record payment in database
        sql = f"""
        INSERT INTO payments (
            id, subscription_id, amount_cents, currency,
            status, created_at, updated_at
        ) VALUES (
            gen_random_uuid(),
            '{body["subscription_id"]}',
            {body["amount_cents"]},
            '{body["currency"]}',
            'pending',
            NOW(),
            NOW()
        )
        RETURNING id
        """
        
        result = await query_db(sql)
        payment_id = result.get("rows", [{}])[0].get("id")
        
        if not payment_id:
            return _error_response(500, "Failed to process payment")
            
        # TODO: Integrate with payment gateway
        # For MVP, just mark as succeeded
        await query_db(f"""
            UPDATE payments
            SET status = 'succeeded',
                updated_at = NOW()
            WHERE id = '{payment_id}'
        """)
        
        return _make_response(201, {
            "payment_id": payment_id,
            "status": "succeeded"
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to process payment: {str(e)}")


async def handle_payment_webhook(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle payment gateway webhook."""
    try:
        # Validate webhook signature
        # TODO: Implement proper signature verification
        
        event_type = body.get("type")
        payment_id = body.get("data", {}).get("id")
        
        if not event_type or not payment_id:
            return _error_response(400, "Invalid webhook payload")
            
        # Update payment status based on webhook event
        if event_type == "payment.succeeded":
            await query_db(f"""
                UPDATE payments
                SET status = 'succeeded',
                    updated_at = NOW()
                WHERE id = '{payment_id}'
            """)
        elif event_type == "payment.failed":
            await query_db(f"""
                UPDATE payments
                SET status = 'failed',
                    updated_at = NOW()
                WHERE id = '{payment_id}'
            """)
            
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
        try:
            body_data = json.loads(body)
            return handle_create_subscription(body_data)
        except json.JSONDecodeError:
            return _error_response(400, "Invalid JSON body")
    
    # POST /revenue/payments
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "payments" and method == "POST":
        if not body:
            return _error_response(400, "Missing request body")
        try:
            body_data = json.loads(body)
            return handle_process_payment(body_data)
        except json.JSONDecodeError:
            return _error_response(400, "Invalid JSON body")
    
    # POST /revenue/webhooks
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "webhooks" and method == "POST":
        if not body:
            return _error_response(400, "Missing request body")
        try:
            body_data = json.loads(body)
            return handle_payment_webhook(body_data)
        except json.JSONDecodeError:
            return _error_response(400, "Invalid JSON body")
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
