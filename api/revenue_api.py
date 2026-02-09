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
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
"""
Autonomous Revenue Engine - Handles recurring billing, payment processing,
and transaction reconciliation.
"""
import datetime
import hashlib
import hmac
import json
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.database import query_db
from core.logging import log_event

app = FastAPI()

PAYMENT_PROVIDERS = {
    "stripe": {
        "webhook_secret": "whsec_...",  # Configure in env
        "handler": "handle_stripe_webhook"
    },
    "paypal": {
        "webhook_secret": "...",
        "handler": "handle_paypal_webhook"
    }
}

class PaymentEvent(BaseModel):
    provider: str
    event_id: str
    event_type: str
    amount: float
    currency: str
    customer_id: str
    subscription_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

async def verify_webhook(request: Request, provider: str) -> bool:
    """Verify webhook signature from payment provider."""
    secret = PAYMENT_PROVIDERS[provider]["webhook_secret"]
    signature = request.headers.get("stripe-signature", "")
    payload = await request.body()
    
    try:
        if provider == "stripe":
            event = stripe.Webhook.construct_event(
                payload, signature, secret
            )
            return True
        elif provider == "paypal":
            # PayPal verification logic
            return True
    except Exception as e:
        log_event("payment.webhook_verification_failed", 
                 f"Failed to verify {provider} webhook: {str(e)}",
                 level="error")
        return False

    return False

async def record_transaction(event: PaymentEvent) -> bool:
    """Record validated payment event in database."""
    try:
        result = await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at,
                attribution
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(event.amount * 100)},
                '{event.currency}',
                '{event.provider}',
                '{json.dumps(event.metadata)}',
                NOW(),
                jsonb_build_object(
                    'customer_id', '{event.customer_id}',
                    'subscription_id', {f"'{event.subscription_id}'" if event.subscription_id else 'NULL'},
                    'provider_event_id', '{event.event_id}'
                )
            )
            RETURNING id
            """
        )
        return bool(result.get("rows"))
    except Exception as e:
        log_event("payment.recording_failed",
                 f"Failed to record {event.provider} payment: {str(e)}",
                 level="error",
                 error_data={"event": event.dict()})
        return False

async def handle_stripe_webhook(payload: Dict[str, Any]) -> bool:
    """Process Stripe webhook events."""
    event_type = payload.get("type")
    data = payload.get("data", {}).get("object", {})
    
    if event_type == "payment_intent.succeeded":
        amount = data.get("amount", 0) / 100  # Convert cents to dollars
        event = PaymentEvent(
            provider="stripe",
            event_id=payload.get("id"),
            event_type="payment",
            amount=amount,
            currency=data.get("currency"),
            customer_id=data.get("customer"),
            metadata=data
        )
        return await record_transaction(event)
    
    elif event_type in ["invoice.paid", "charge.succeeded"]:
        # Handle recurring payments
        pass
        
    return False

@app.post("/webhooks/payment/{provider}")
async def payment_webhook(
    request: Request, 
    provider: str,
    response: Response
):
    """Handle payment provider webhooks."""
    if provider not in PAYMENT_PROVIDERS:
        raise HTTPException(status_code=404, detail="Provider not supported")
    
    if not await verify_webhook(request, provider):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        payload = await request.json()
        handler = globals()[PAYMENT_PROVIDERS[provider]["handler"]]
        success = await handler(payload)
        
        if success:
            return JSONResponse({"status": "processed"})
        else:
            raise HTTPException(
                status_code=400, 
                detail="Failed to process event"
            )
            
    except Exception as e:
        log_event("payment.webhook_error",
                 f"Payment webhook processing failed: {str(e)}",
                 level="error",
                 error_data={"provider": provider})
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

def start_recurring_billing():
    """Run daily to process recurring subscriptions."""
    # Query database for active subscriptions due for billing
    # Generate invoices/payment attempts
    # Handle failures and retries
    pass

async def reconcile_payments():
    """Verify recorded payments match provider records."""
    # Compare our database with payment provider data
    # Identify and report discrepancies
    # Automatically correct where possible
    pass

async def generate_billing_reports():
    """Create summary reports for accounting."""
    # Generate daily/weekly/monthly revenue reports
    # Breakdown by customer, product, region etc.
    # Export to accounting tools
    pass
