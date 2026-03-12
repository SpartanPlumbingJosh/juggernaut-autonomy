"""
Payment API - Handle payment processing and subscriptions.
"""
import json
from typing import Any, Dict, Optional

from core.database import query_db
from api.payment_service import PaymentService

payment_service = PaymentService()

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

async def handle_checkout(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Create checkout session."""
    try:
        customer_id = query_params.get("customer_id")
        price_id = query_params.get("price_id")
        
        if not customer_id or not price_id:
            return _make_response(400, {"error": "Missing required parameters"})
            
        result = await payment_service.create_checkout_session(
            customer_id=customer_id,
            price_id=price_id,
            success_url=query_params.get("success_url", ""),
            cancel_url=query_params.get("cancel_url", ""),
            metadata={"user_id": query_params.get("user_id", "")}
        )
        
        if not result["success"]:
            return _make_response(500, {"error": result["error"]})
            
        return _make_response(200, {
            "session_id": result["session_id"],
            "checkout_url": result["url"]
        })
    except Exception as e:
        return _make_response(500, {"error": str(e)})

async def handle_webhook(body: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """Process payment webhook."""
    try:
        sig_header = headers.get("Stripe-Signature", "")
        result = await payment_service.handle_webhook(body.encode(), sig_header)
        
        if not result["success"]:
            return _make_response(400, {"error": result["error"]})
            
        return _make_response(200, {"status": "processed"})
    except Exception as e:
        return _make_response(500, {"error": str(e)})

async def handle_billing_portal(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate billing portal URL."""
    try:
        customer_id = query_params.get("customer_id")
        if not customer_id:
            return _make_response(400, {"error": "Missing customer_id"})
            
        result = await payment_service.get_billing_portal_url(customer_id)
        
        if not result["success"]:
            return _make_response(500, {"error": result["error"]})
            
        return _make_response(200, {"portal_url": result["url"]})
    except Exception as e:
        return _make_response(500, {"error": str(e)})

async def handle_subscription_status(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Check subscription status."""
    try:
        subscription_id = query_params.get("subscription_id")
        if not subscription_id:
            return _make_response(400, {"error": "Missing subscription_id"})
            
        result = await payment_service.get_subscription_status(subscription_id)
        
        if not result["success"]:
            return _make_response(404, {"error": result["error"]})
            
        return _make_response(200, {
            "status": result["status"],
            "active": result["active"],
            "current_period_end": result["current_period_end"]
        })
    except Exception as e:
        return _make_response(500, {"error": str(e)})

def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Route payment API requests."""
    headers = headers or {}
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    parts = [p for p in path.split("/") if p]
    
    # POST /payment/checkout
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "checkout" and method == "POST":
        return handle_checkout(query_params)
    
    # POST /payment/webhook
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "webhook" and method == "POST":
        return handle_webhook(body or "", headers)
    
    # GET /payment/portal
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "portal" and method == "GET":
        return handle_billing_portal(query_params)
    
    # GET /payment/status
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "status" and method == "GET":
        return handle_subscription_status(query_params)
    
    return _make_response(404, {"error": "Not found"})

__all__ = ["route_request"]
