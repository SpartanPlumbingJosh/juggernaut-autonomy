"""
Customer Self-Service Portal API

Endpoints:
- GET /portal/subscriptions - Get customer subscriptions
- POST /portal/subscriptions - Create new subscription
- GET /portal/invoices - Get customer invoices
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json

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


async def handle_get_subscriptions(customer_id: str) -> Dict[str, Any]:
    """Get customer's active subscriptions."""
    try:
        res = await query_db(f"""
            SELECT id, plan_id, status, current_period_end, created_at
            FROM subscriptions
            WHERE customer_id = '{customer_id}'
              AND status = 'active'
            ORDER BY created_at DESC
        """)
        return _make_response(200, {"subscriptions": res.get("rows", [])})
    except Exception as e:
        return _error_response(500, f"Failed to get subscriptions: {str(e)}")


async def handle_create_subscription(customer_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create new subscription."""
    try:
        plan_id = body.get("plan_id")
        if not plan_id:
            return _error_response(400, "Missing plan_id")
            
        # Insert new subscription
        res = await query_db(f"""
            INSERT INTO subscriptions (
                id, customer_id, plan_id, status,
                current_period_end, created_at
            ) VALUES (
                gen_random_uuid(),
                '{customer_id}',
                '{plan_id}',
                'active',
                NOW() + INTERVAL '1 month',
                NOW()
            )
            RETURNING id
        """)
        
        return _make_response(201, {
            "subscription_id": res.get("rows", [{}])[0].get("id")
        })
    except Exception as e:
        return _error_response(500, f"Failed to create subscription: {str(e)}")


async def handle_get_invoices(customer_id: str) -> Dict[str, Any]:
    """Get customer's invoices."""
    try:
        res = await query_db(f"""
            SELECT id, amount_cents, currency, status, created_at
            FROM invoices
            WHERE customer_id = '{customer_id}'
            ORDER BY created_at DESC
            LIMIT 50
        """)
        return _make_response(200, {"invoices": res.get("rows", [])})
    except Exception as e:
        return _error_response(500, f"Failed to get invoices: {str(e)}")


def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route customer portal requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # Get customer ID from auth
    customer_id = query_params.get("customer_id", [""])[0]
    if not customer_id:
        return _error_response(401, "Unauthorized")
    
    # GET /portal/subscriptions
    if len(parts) == 2 and parts[0] == "portal" and parts[1] == "subscriptions" and method == "GET":
        return handle_get_subscriptions(customer_id)
    
    # POST /portal/subscriptions
    if len(parts) == 2 and parts[0] == "portal" and parts[1] == "subscriptions" and method == "POST":
        return handle_create_subscription(customer_id, json.loads(body or "{}"))
    
    # GET /portal/invoices
    if len(parts) == 2 and parts[0] == "portal" and parts[1] == "invoices" and method == "GET":
        return handle_get_invoices(customer_id)
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
