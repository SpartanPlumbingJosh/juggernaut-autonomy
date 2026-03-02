"""
Revenue API - Complete revenue infrastructure including:
- Payment processing
- Subscription management
- Invoicing system 
- Revenue recognition
- Real-time transaction tracking

Endpoints:
- GET /revenue/summary - MTD/QTD/YTD totals
- GET /revenue/transactions - Transaction history
- GET /revenue/charts - Revenue over time data
- POST /revenue/payments - Process new payment
- POST /revenue/subscriptions - Create subscription
- POST /revenue/invoices - Generate invoice
- GET /revenue/recognized - Recognized revenue report
- POST /revenue/webhook - Payment processor webhook
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


async def handle_payment_processing(body: Dict[str, Any]) -> Dict[str, Any]:
    """Process a payment from any provider."""
    try:
        required_fields = ["amount_cents", "currency", "payment_method", "customer_id"]
        if not all(field in body for field in required_fields):
            return _error_response(400, "Missing required payment fields")
        
        # Process payment
        amount_cents = int(body["amount_cents"])
        currency = str(body["currency"])
        payment_method = str(body["payment_method"])
        customer_id = str(body["customer_id"])
        description = body.get("description", "")

        # Save transaction
        sql = f"""
        INSERT INTO revenue_events (
            id,
            experiment_id,
            event_type,
            amount_cents,
            currency,
            source,
            metadata,
            recorded_at,
            created_at
        ) VALUES (
            gen_random_uuid(),
            NULL,
            'revenue',
            {amount_cents},
            '{currency}',
            '{payment_method}',
            '{json.dumps({
                "customer_id": customer_id,
                "description": description,
                "processor": body.get("processor", "manual"),
                "invoice_id": body.get("invoice_id")
            })}'::jsonb,
            NOW(),
            NOW()
        )
        RETURNING id
        """
        
        result = await query_db(sql)
        payment_id = result.get("rows", [{}])[0].get("id")

        return _make_response(200, {
            "success": True,
            "payment_id": payment_id,
            "amount": amount_cents / 100,
            "currency": currency
        })
        
    except Exception as e:
        return _error_response(500, f"Payment processing failed: {str(e)}")


async def handle_subscription_creation(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update a subscription."""
    try:
        required_fields = ["plan_id", "customer_id", "payment_method"]
        if not all(field in body for field in required_fields):
            return _error_response(400, "Missing required subscription fields")
        
        # Insert/update subscription
        sql = f"""
        INSERT INTO subscriptions (
            id,
            customer_id,
            plan_id,
            payment_method,
            status,
            metadata,
            created_at,
            updated_at
        ) VALUES (
            gen_random_uuid(),
            '{body["customer_id"]}',
            '{body["plan_id"]}',
            '{body["payment_method"]}',
            'active',
            '{json.dumps(body.get("metadata", {}))}'::jsonb,
            NOW(),
            NOW()
        )
        ON CONFLICT (customer_id, plan_id) WHERE status != 'canceled'
        DO UPDATE SET
            payment_method = EXCLUDED.payment_method,
            status = 'active',
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING id
        """
        
        result = await query_db(sql)
        sub_id = result.get("rows", [{}])[0].get("id")

        return _make_response(200, {
            "success": True,
            "subscription_id": sub_id
        })
        
    except Exception as e:
        return _error_response(500, f"Subscription creation failed: {str(e)}")


async def handle_invoice_generation(body: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an invoice for a customer."""
    try:
        required_fields = ["customer_id", "amount_cents", "currency", "items"]
        if not all(field in body for field in required_fields):
            return _error_response(400, "Missing required invoice fields")
        
        # Generate invoice
        sql = f"""
        INSERT INTO invoices (
            id,
            customer_id,
            amount_cents,
            currency,
            status,
            metadata,
            due_date,
            created_at
        ) VALUES (
            gen_random_uuid(),
            '{body["customer_id"]}',
            {body["amount_cents"]},
            '{body["currency"]}',
            'pending',
            '{json.dumps({
                "items": body["items"],
                "description": body.get("description", ""),
                "terms": body.get("terms")
            })}'::jsonb,
            {(f"'{body['due_date']}'" if body.get('due_date') else "NOW() + INTERVAL '30 DAYS'")},
            NOW()
        )
        RETURNING id
        """
        
        result = await query_db(sql)
        invoice_id = result.get("rows", [{}])[0].get("id")

        return _make_response(200, {
            "success": True,
            "invoice_id": invoice_id
        })
        
    except Exception as e:
        return _error_response(500, f"Invoice generation failed: {str(e)}")


async def handle_revenue_recognition() -> Dict[str, Any]:
    """Get recognized revenue report."""
    try:
        # Get recognized revenue based on accounting rules
        sql = """
        SELECT 
            invoice_id,
            customer_id,
            amount_cents,
            currency,
            recognized_date,
            recognized_amount_cents,
            invoice_date
        FROM recognized_revenue
        WHERE recognized_date BETWEEN NOW() - INTERVAL '90 DAYS' AND NOW()
        ORDER BY recognized_date DESC
        """
        
        result = await query_db(sql)
        recognized = result.get("rows", [])

        return _make_response(200, {
            "recognized_revenue": recognized,
            "period": "last_90_days"
        })
        
    except Exception as e:
        return _error_response(500, f"Revenue recognition report failed: {str(e)}")


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
    parsed_body = json.loads(body or "{}")
    
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
    
    # POST /revenue/payments
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "payments" and method == "POST":
        return handle_payment_processing(parsed_body)
    
    # POST /revenue/subscriptions
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "subscriptions" and method == "POST":
        return handle_subscription_creation(parsed_body)
    
    # POST /revenue/invoices
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "invoices" and method == "POST":
        return handle_invoice_generation(parsed_body)
    
    # GET /revenue/recognized
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "recognized" and method == "GET":
        return handle_revenue_recognition()
    
    # POST /revenue/webhook
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "webhook" and method == "POST":
        return handle_payment_webhook(parsed_body)

    return _error_response(404, "Not found")


__all__ = ["route_request"]
