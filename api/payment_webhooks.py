"""
Payment Webhooks - Handle Stripe/PayPal payment events and record revenue.
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
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(body)
    }


async def handle_stripe_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process Stripe payment webhook event."""
    try:
        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})
        
        if event_type == "payment_intent.succeeded":
            amount = data.get("amount", 0)  # In cents
            currency = data.get("currency", "usd")
            customer_email = data.get("receipt_email", "")
            payment_id = data.get("id", "")
            
            # Record revenue event
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {amount},
                    '{currency}',
                    'stripe',
                    '{json.dumps({
                        "payment_id": payment_id,
                        "customer_email": customer_email
                    })}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            
            return _make_response(200, {"success": True})
            
        return _make_response(200, {"success": True, "message": "Event not processed"})
        
    except Exception as e:
        return _make_response(500, {"error": str(e)})


async def handle_paypal_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process PayPal payment webhook event."""
    try:
        event_type = event.get("event_type")
        resource = event.get("resource", {})
        
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            amount = float(resource.get("amount", {}).get("value", 0)) * 100  # Convert to cents
            currency = resource.get("amount", {}).get("currency_code", "usd")
            payment_id = resource.get("id", "")
            payer_email = resource.get("payer", {}).get("email_address", "")
            
            # Record revenue event
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {amount},
                    '{currency}',
                    'paypal',
                    '{json.dumps({
                        "payment_id": payment_id,
                        "payer_email": payer_email
                    })}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            
            return _make_response(200, {"success": True})
            
        return _make_response(200, {"success": True, "message": "Event not processed"})
        
    except Exception as e:
        return _make_response(500, {"error": str(e)})


def route_webhook_request(source: str, body: str) -> Dict[str, Any]:
    """Route payment webhook requests."""
    try:
        event = json.loads(body)
        
        if source == "stripe":
            return handle_stripe_webhook(event)
        elif source == "paypal":
            return handle_paypal_webhook(event)
        else:
            return _make_response(400, {"error": "Unsupported payment source"})
            
    except json.JSONDecodeError:
        return _make_response(400, {"error": "Invalid JSON"})
    except Exception as e:
        return _make_response(500, {"error": str(e)})


__all__ = ["route_webhook_request"]
