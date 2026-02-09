"""
Payment Webhooks - Handle payment processing notifications and trigger fulfillment.
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
    """Process Stripe payment webhook events."""
    try:
        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})
        
        if event_type == "payment_intent.succeeded":
            # Record successful payment
            amount = data.get("amount", 0)
            currency = data.get("currency", "usd")
            customer_email = data.get("receipt_email", "")
            metadata = data.get("metadata", {})
            
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
                    '{json.dumps(metadata)}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            
            # Trigger fulfillment
            await fulfill_order(customer_email, metadata)
            
            return _make_response(200, {"status": "processed"})
            
        return _make_response(200, {"status": "skipped"})
        
    except Exception as e:
        return _make_response(500, {"error": str(e)})


async def fulfill_order(email: str, metadata: Dict[str, Any]) -> None:
    """Automatically fulfill an order."""
    product_id = metadata.get("product_id")
    quantity = metadata.get("quantity", 1)
    
    # TODO: Implement product-specific fulfillment logic
    # This could include:
    # - Sending digital product access
    # - Triggering service provisioning
    # - Adding to subscription management
    # - Sending confirmation emails
    
    # Example: Record fulfillment
    await query_db(f"""
        INSERT INTO fulfillments (
            id, product_id, quantity, customer_email,
            status, created_at, updated_at
        ) VALUES (
            gen_random_uuid(),
            '{product_id}',
            {quantity},
            '{email}',
            'pending',
            NOW(),
            NOW()
        )
    """)


def route_webhook_request(path: str, method: str, body: Optional[str] = None) -> Dict[str, Any]:
    """Route payment webhook requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # POST /webhooks/stripe
    if len(parts) == 2 and parts[0] == "webhooks" and parts[1] == "stripe" and method == "POST":
        if not body:
            return _make_response(400, {"error": "Missing body"})
        try:
            event = json.loads(body)
            return handle_stripe_webhook(event)
        except Exception as e:
            return _make_response(400, {"error": str(e)})
    
    return _make_response(404, {"error": "Not found"})


__all__ = ["route_webhook_request"]
```

Now let's enhance the revenue API to include product metrics:

api/revenue_api.py
```python
<<<<<<< SEARCH
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
