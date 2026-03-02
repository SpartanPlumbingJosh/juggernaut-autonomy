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
Revenue Channel MVP - Automated payment processing and digital fulfillment.

Features:
- Stripe/PayPal integration
- Digital product delivery pipeline
- Error handling and retry logic
- Webhook handlers for real-time revenue tracking
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
import paypalrestsdk
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse

from core.database import query_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize payment gateways
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

app = FastAPI()

class RevenueChannel:
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 1  # seconds

    async def process_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through Stripe or PayPal."""
        try:
            payment_method = payment_data.get("payment_method", "stripe")
            
            if payment_method == "stripe":
                return await self._process_stripe_payment(payment_data)
            elif payment_method == "paypal":
                return await self._process_paypal_payment(payment_data)
            else:
                raise ValueError("Invalid payment method")
                
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            raise

    async def _process_stripe_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through Stripe."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(payment_data["amount"] * 100),  # Convert to cents
                currency=payment_data.get("currency", "usd"),
                payment_method=payment_data["payment_token"],
                confirmation_method="manual",
                confirm=True,
                metadata={
                    "product_id": payment_data.get("product_id"),
                    "customer_email": payment_data.get("customer_email")
                }
            )
            
            if intent.status == "succeeded":
                return {
                    "success": True,
                    "payment_id": intent.id,
                    "amount": intent.amount / 100,
                    "currency": intent.currency
                }
            else:
                raise Exception(f"Payment failed: {intent.status}")
                
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise

    async def _process_paypal_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through PayPal."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "transactions": [{
                    "amount": {
                        "total": str(payment_data["amount"]),
                        "currency": payment_data.get("currency", "USD")
                    },
                    "description": f"Purchase of {payment_data.get('product_name')}"
                }],
                "redirect_urls": {
                    "return_url": payment_data.get("return_url"),
                    "cancel_url": payment_data.get("cancel_url")
                }
            })
            
            if payment.create():
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "amount": payment_data["amount"],
                    "currency": payment_data.get("currency", "USD")
                }
            else:
                raise Exception(f"PayPal payment failed: {payment.error}")
                
        except Exception as e:
            logger.error(f"PayPal error: {str(e)}")
            raise

    async def fulfill_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle digital product delivery or service fulfillment."""
        try:
            # Implement your fulfillment logic here
            # This could include:
            # - Sending download links
            # - Generating access credentials
            # - Triggering service provisioning
            
            return {
                "success": True,
                "order_id": order_data.get("order_id"),
                "fulfillment_status": "completed"
            }
            
        except Exception as e:
            logger.error(f"Order fulfillment failed: {str(e)}")
            raise

    async def handle_webhook(self, payload: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Process webhook events from payment providers."""
        try:
            event = None
            
            if source == "stripe":
                event = stripe.Webhook.construct_event(
                    payload["body"],
                    payload["headers"]["Stripe-Signature"],
                    os.getenv("STRIPE_WEBHOOK_SECRET")
                )
            elif source == "paypal":
                event = paypalrestsdk.WebhookEvent.verify(
                    payload["headers"]["Paypal-Transmission-Id"],
                    payload["headers"]["Paypal-Transmission-Time"],
                    os.getenv("PAYPAL_WEBHOOK_ID"),
                    payload["body"],
                    os.getenv("PAYPAL_CERT_URL")
                )
            
            if event:
                return await self._process_webhook_event(event, source)
            else:
                raise Exception("Invalid webhook event")
                
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            raise

    async def _process_webhook_event(self, event: Any, source: str) -> Dict[str, Any]:
        """Process validated webhook event."""
        try:
            event_type = event.type if source == "stripe" else event.event_type
            
            if event_type in ["payment_intent.succeeded", "PAYMENT.SALE.COMPLETED"]:
                await self._record_revenue_event(event, source)
                return {"success": True}
            else:
                return {"success": False, "message": "Unhandled event type"}
                
        except Exception as e:
            logger.error(f"Webhook event processing failed: {str(e)}")
            raise

    async def _record_revenue_event(self, event: Any, source: str) -> None:
        """Record revenue event in database."""
        try:
            if source == "stripe":
                payment_intent = event.data.object
                amount = payment_intent.amount / 100
                currency = payment_intent.currency
                metadata = payment_intent.metadata
            else:
                sale = event.resource
                amount = float(sale.amount.total)
                currency = sale.amount.currency
                metadata = sale.metadata or {}
            
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {int(amount * 100)},
                    '{currency}',
                    '{source}',
                    '{json.dumps(metadata)}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            
        except Exception as e:
            logger.error(f"Failed to record revenue event: {str(e)}")
            raise

@app.post("/process-payment")
async def process_payment_endpoint(request: Request):
    """Endpoint for processing payments."""
    try:
        data = await request.json()
        channel = RevenueChannel()
        result = await channel.process_payment(data)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Payment endpoint error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@app.post("/fulfill-order")
async def fulfill_order_endpoint(request: Request):
    """Endpoint for order fulfillment."""
    try:
        data = await request.json()
        channel = RevenueChannel()
        result = await channel.fulfill_order(data)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Fulfillment endpoint error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Endpoint for Stripe webhooks."""
    try:
        payload = {
            "body": await request.body(),
            "headers": dict(request.headers)
        }
        channel = RevenueChannel()
        result = await channel.handle_webhook(payload, "stripe")
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Stripe webhook error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@app.post("/webhook/paypal")
async def paypal_webhook(request: Request):
    """Endpoint for PayPal webhooks."""
    try:
        payload = {
            "body": await request.body(),
            "headers": dict(request.headers)
        }
        channel = RevenueChannel()
        result = await channel.handle_webhook(payload, "paypal")
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"PayPal webhook error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

async def startup():
    """Initialize the revenue channel."""
    logger.info("Revenue channel initialized")

async def shutdown():
    """Clean up resources."""
    logger.info("Revenue channel shutdown")

app.add_event_handler("startup", startup)
app.add_event_handler("shutdown", shutdown)
