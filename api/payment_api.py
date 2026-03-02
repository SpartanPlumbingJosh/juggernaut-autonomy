"""
Payment API - Handle payment processing, subscriptions, and revenue tracking.

Endpoints:
- POST /payment/webhook - Handle payment provider webhooks
- POST /payment/subscribe - Create new subscription
- POST /payment/invoice - Generate invoice
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

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


async def handle_payment_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process payment provider webhook events."""
    try:
        event_type = event.get("type")
        data = event.get("data", {})
        
        # Handle different payment events
        if event_type == "payment.succeeded":
            await log_revenue_event(
                amount_cents=int(float(data.get("amount")) * 100),
                currency=data.get("currency"),
                source="payment",
                event_type="revenue",
                metadata={
                    "payment_id": data.get("id"),
                    "customer": data.get("customer"),
                    "invoice_id": data.get("invoice")
                }
            )
        elif event_type == "payment.refunded":
            await log_revenue_event(
                amount_cents=-int(float(data.get("amount")) * 100),
                currency=data.get("currency"),
                source="payment",
                event_type="revenue",
                metadata={
                    "payment_id": data.get("id"),
                    "customer": data.get("customer"),
                    "invoice_id": data.get("invoice")
                }
            )
        elif event_type == "subscription.created":
            await create_subscription(data)
        elif event_type == "subscription.updated":
            await update_subscription(data)
            
        return _make_response(200, {"success": True})
        
    except Exception as e:
        return _error_response(500, f"Failed to process webhook: {str(e)}")


async def log_revenue_event(
    amount_cents: int,
    currency: str,
    source: str,
    event_type: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Log a revenue event to the database."""
    metadata_json = json.dumps(metadata or {})
    await query_db(f"""
        INSERT INTO revenue_events (
            id, amount_cents, currency, source, event_type, 
            metadata, recorded_at, created_at
        ) VALUES (
            gen_random_uuid(),
            {amount_cents},
            '{currency}',
            '{source}',
            '{event_type}',
            '{metadata_json}'::jsonb,
            NOW(),
            NOW()
        )
    """)


async def create_subscription(data: Dict[str, Any]) -> None:
    """Create a new subscription record."""
    await query_db(f"""
        INSERT INTO subscriptions (
            id, customer_id, plan_id, status, 
            current_period_start, current_period_end,
            created_at, updated_at, metadata
        ) VALUES (
            gen_random_uuid(),
            '{data.get("customer")}',
            '{data.get("plan")}',
            'active',
            '{data.get("current_period_start")}',
            '{data.get("current_period_end")}',
            NOW(),
            NOW(),
            '{json.dumps(data)}'::jsonb
        )
    """)


async def update_subscription(data: Dict[str, Any]) -> None:
    """Update an existing subscription record."""
    await query_db(f"""
        UPDATE subscriptions SET
            status = '{data.get("status")}',
            current_period_start = '{data.get("current_period_start")}',
            current_period_end = '{data.get("current_period_end")}',
            updated_at = NOW(),
            metadata = '{json.dumps(data)}'::jsonb
        WHERE id = '{data.get("id")}'
    """)


def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route payment API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # POST /payment/webhook
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "webhook" and method == "POST":
        if not body:
            return _error_response(400, "Missing request body")
        try:
            event = json.loads(body)
            return handle_payment_webhook(event)
        except json.JSONDecodeError:
            return _error_response(400, "Invalid JSON")
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
