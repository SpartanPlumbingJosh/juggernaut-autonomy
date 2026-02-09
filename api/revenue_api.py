"""
Revenue API - Expose revenue tracking and monetization features.

Endpoints:
- GET /revenue/summary - MTD/QTD/YTD totals
- GET /revenue/transactions - Transaction history
- GET /revenue/charts - Revenue over time data
- POST /revenue/subscriptions - Create new subscriptions
- POST /revenue/payments - Record direct payments
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.database import query_db
from .revenue_service import handle_create_subscription, handle_record_payment


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
        return await handle_create_subscription(
            headers.get("Authorization", ""),
            json.loads(body) if body else {}
        )
    
    # POST /revenue/payments
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "payments" and method == "POST":
        return await handle_record_payment(
            headers.get("Authorization", ""),
            json.loads(body) if body else {}
        )
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
"""
Revenue Service - Core business logic for monetization features.
Handles subscriptions, billing, and customer management.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.database import query_db
from core.auth import validate_api_key


class RevenueService:
    """Core service for handling revenue operations."""
    
    def __init__(self, db_conn):
        self.db = db_conn

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: str) -> Dict:
        """Create a new paid subscription."""
        sub_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        try:
            await query_db(f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, 
                    status, created_at, updated_at,
                    payment_method, billing_cycle_start
                ) VALUES (
                    '{sub_id}', '{customer_id}', '{plan_id}',
                    'active', '{now}', '{now}',
                    '{payment_method}', '{now}'
                )
            """)
            
            # Record initial payment event
            plan = await self.get_plan(plan_id)
            await self.record_payment(
                customer_id=customer_id,
                amount_cents=int(plan['price_cents']),
                currency=plan['currency'],
                source='subscription',
                reference_id=sub_id
            )
            
            return {"success": True, "subscription_id": sub_id}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_plan(self, plan_id: str) -> Dict:
        """Get pricing plan details."""
        result = await query_db(f"""
            SELECT id, name, price_cents, currency, billing_interval 
            FROM pricing_plans 
            WHERE id = '{plan_id}'
        """)
        return result.get("rows", [{}])[0]

    async def record_payment(
        self,
        customer_id: str,
        amount_cents: int,
        currency: str,
        source: str,
        reference_id: str
    ) -> Dict:
        """Record a successful payment."""
        payment_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        try:
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, customer_id, reference_id,
                    recorded_at, created_at
                ) VALUES (
                    '{payment_id}', 'revenue', {amount_cents}, '{currency}',
                    '{source}', '{customer_id}', '{reference_id}',
                    '{now}', '{now}'
                )
            """)
            return {"success": True, "payment_id": payment_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def cancel_subscription(self, subscription_id: str) -> Dict:
        """Cancel an existing subscription."""
        try:
            await query_db(f"""
                UPDATE subscriptions
                SET status = 'canceled',
                    updated_at = NOW()
                WHERE id = '{subscription_id}'
            """)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def handle_create_subscription(auth_header: str, body: Dict) -> Dict:
    """API handler for creating subscriptions."""
    auth = validate_api_key(auth_header)
    if not auth.get("valid"):
        return {"statusCode": 401, "body": {"error": "Unauthorized"}}
    
    service = RevenueService(query_db)
    customer_id = body.get("customer_id")
    plan_id = body.get("plan_id")
    payment_method = body.get("payment_method", "stripe")
    
    if not all([customer_id, plan_id]):
        return {"statusCode": 400, "body": {"error": "Missing required fields"}}
    
    result = await service.create_subscription(customer_id, plan_id, payment_method)
    status_code = 200 if result["success"] else 400
    return {"statusCode": status_code, "body": result}


async def handle_record_payment(auth_header: str, body: Dict) -> Dict:
    """API handler for recording payments."""
    auth = validate_api_key(auth_header)
    if not auth.get("valid"):
        return {"statusCode": 401, "body": {"error": "Unauthorized"}}
    
    service = RevenueService(query_db)
    required = ["customer_id", "amount_cents", "currency", "source"]
    if not all(field in body for field in required):
        return {"statusCode": 400, "body": {"error": "Missing required fields"}}
    
    result = await service.record_payment(
        customer_id=body["customer_id"],
        amount_cents=body["amount_cents"],
        currency=body["currency"],
        source=body["source"],
        reference_id=body.get("reference_id", "")
    )
    status_code = 200 if result["success"] else 400
    return {"statusCode": status_code, "body": result}
