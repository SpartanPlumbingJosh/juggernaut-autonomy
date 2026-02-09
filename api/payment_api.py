"""
Payment API - Handle payment processing, subscriptions, and billing.

Endpoints:
- POST /payment/webhook - Handle payment provider webhooks
- POST /payment/subscribe - Create new subscription
- GET /payment/invoices - Get invoice history
- POST /payment/meter - Record usage for metered billing
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db
from core.payment_processor import PaymentProcessor

def _make_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(body)
    }

async def handle_payment_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process payment provider webhook events."""
    try:
        processor = PaymentProcessor()
        event_type = event.get("type")
        data = event.get("data", {})
        
        # Handle different webhook events
        if event_type == "payment.succeeded":
            await processor.handle_payment_success(data)
        elif event_type == "payment.failed":
            await processor.handle_payment_failure(data)
        elif event_type == "invoice.payment_succeeded":
            await processor.handle_invoice_payment(data)
        elif event_type == "customer.subscription.created":
            await processor.handle_subscription_created(data)
        elif event_type == "customer.subscription.updated":
            await processor.handle_subscription_updated(data)
        elif event_type == "customer.subscription.deleted":
            await processor.handle_subscription_deleted(data)
            
        return _make_response(200, {"success": True})
    except Exception as e:
        return _make_response(500, {"error": str(e)})

async def handle_create_subscription(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create new subscription."""
    try:
        processor = PaymentProcessor()
        customer_id = body.get("customer_id")
        plan_id = body.get("plan_id")
        payment_method_id = body.get("payment_method_id")
        
        subscription = await processor.create_subscription(
            customer_id=customer_id,
            plan_id=plan_id,
            payment_method_id=payment_method_id
        )
        
        return _make_response(200, {"subscription": subscription})
    except Exception as e:
        return _make_response(500, {"error": str(e)})

async def handle_get_invoices(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Get invoice history."""
    try:
        processor = PaymentProcessor()
        customer_id = query_params.get("customer_id")
        limit = int(query_params.get("limit", 10))
        offset = int(query_params.get("offset", 0))
        
        invoices = await processor.get_invoices(
            customer_id=customer_id,
            limit=limit,
            offset=offset
        )
        
        return _make_response(200, {"invoices": invoices})
    except Exception as e:
        return _make_response(500, {"error": str(e)})

async def handle_record_usage(body: Dict[str, Any]) -> Dict[str, Any]:
    """Record usage for metered billing."""
    try:
        processor = PaymentProcessor()
        subscription_id = body.get("subscription_id")
        quantity = int(body.get("quantity", 1))
        timestamp = datetime.now(timezone.utc).isoformat()
        
        await processor.record_usage(
            subscription_id=subscription_id,
            quantity=quantity,
            timestamp=timestamp
        )
        
        return _make_response(200, {"success": True})
    except Exception as e:
        return _make_response(500, {"error": str(e)})

def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route payment API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # POST /payment/webhook
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "webhook" and method == "POST":
        return handle_payment_webhook(json.loads(body or "{}"))
    
    # POST /payment/subscribe
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "subscribe" and method == "POST":
        return handle_create_subscription(json.loads(body or "{}"))
    
    # GET /payment/invoices
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "invoices" and method == "GET":
        return handle_get_invoices(query_params)
    
    # POST /payment/meter
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "meter" and method == "POST":
        return handle_record_usage(json.loads(body or "{}"))
    
    return _make_response(404, {"error": "Not found"})

__all__ = ["route_request"]
