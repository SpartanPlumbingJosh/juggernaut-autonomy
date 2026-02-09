"""
Revenue API - Handle all revenue operations including subscriptions, billing, and service delivery.

Endpoints:
- GET /revenue/summary - MTD/QTD/YTD totals
- GET /revenue/transactions - Transaction history
- GET /revenue/charts - Revenue over time data
- POST /revenue/subscriptions - Create new subscription
- POST /revenue/billing - Process billing event
- POST /revenue/onboarding - Complete customer onboarding
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import uuid

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


async def handle_subscription_creation(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new subscription."""
    try:
        customer_id = body.get("customer_id")
        plan_id = body.get("plan_id")
        billing_cycle = body.get("billing_cycle", "monthly")
        start_date = body.get("start_date", datetime.now(timezone.utc).isoformat())
        
        # Validate required fields
        if not customer_id or not plan_id:
            return _error_response(400, "Missing required fields: customer_id and plan_id are required")
        
        # Create subscription record
        subscription_id = str(uuid.uuid4())
        sql = f"""
        INSERT INTO subscriptions (
            id, customer_id, plan_id, billing_cycle, 
            status, start_date, created_at, updated_at
        ) VALUES (
            '{subscription_id}',
            '{customer_id}',
            '{plan_id}',
            '{billing_cycle}',
            'active',
            '{start_date}',
            NOW(),
            NOW()
        )
        """
        await query_db(sql)
        
        # Create initial billing event
        billing_event = {
            "subscription_id": subscription_id,
            "event_type": "subscription_created",
            "amount_cents": 0,
            "currency": "USD",
            "metadata": {
                "plan_id": plan_id,
                "billing_cycle": billing_cycle
            }
        }
        await _create_billing_event(billing_event)
        
        return _make_response(201, {
            "subscription_id": subscription_id,
            "status": "active",
            "start_date": start_date
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to create subscription: {str(e)}")


async def _create_billing_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a billing event record."""
    event_id = str(uuid.uuid4())
    sql = f"""
    INSERT INTO billing_events (
        id, subscription_id, event_type, amount_cents,
        currency, metadata, created_at
    ) VALUES (
        '{event_id}',
        '{event_data.get("subscription_id")}',
        '{event_data.get("event_type")}',
        {event_data.get("amount_cents", 0)},
        '{event_data.get("currency", "USD")}',
        '{json.dumps(event_data.get("metadata", {}))}',
        NOW()
    )
    """
    return await query_db(sql)


async def handle_billing_event(body: Dict[str, Any]) -> Dict[str, Any]:
    """Process a billing event."""
    try:
        required_fields = ["subscription_id", "event_type", "amount_cents"]
        if not all(field in body for field in required_fields):
            return _error_response(400, f"Missing required fields: {', '.join(required_fields)}")
        
        # Create billing event
        result = await _create_billing_event(body)
        
        # Update revenue events if this is a payment
        if body["event_type"] == "payment":
            revenue_event = {
                "event_type": "revenue",
                "amount_cents": body["amount_cents"],
                "currency": body.get("currency", "USD"),
                "source": "subscription",
                "metadata": {
                    "subscription_id": body["subscription_id"],
                    "billing_event_id": result.get("id")
                }
            }
            await _create_revenue_event(revenue_event)
        
        return _make_response(201, {"success": True, "event_id": result.get("id")})
        
    except Exception as e:
        return _error_response(500, f"Failed to process billing event: {str(e)}")


async def handle_customer_onboarding(body: Dict[str, Any]) -> Dict[str, Any]:
    """Complete customer onboarding."""
    try:
        required_fields = ["customer_id", "plan_id"]
        if not all(field in body for field in required_fields):
            return _error_response(400, f"Missing required fields: {', '.join(required_fields)}")
        
        # Create subscription
        subscription = await handle_subscription_creation(body)
        if subscription.get("statusCode", 200) != 201:
            return subscription
        
        # Trigger initial billing
        billing_event = {
            "subscription_id": subscription["body"]["subscription_id"],
            "event_type": "initial_payment",
            "amount_cents": body.get("initial_payment_cents", 0),
            "currency": body.get("currency", "USD"),
            "metadata": {
                "onboarding": True
            }
        }
        await handle_billing_event(billing_event)
        
        return _make_response(201, {
            "success": True,
            "subscription_id": subscription["body"]["subscription_id"],
            "onboarding_complete": True
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to complete onboarding: {str(e)}")


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
        return handle_subscription_creation(json.loads(body or "{}"))
    
    # POST /revenue/billing
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "billing" and method == "POST":
        return handle_billing_event(json.loads(body or "{}"))
    
    # POST /revenue/onboarding
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "onboarding" and method == "POST":
        return handle_customer_onboarding(json.loads(body or "{}"))
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
