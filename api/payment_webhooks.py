"""
Payment Webhooks - Handle payment events and trigger service delivery.

Endpoints:
- POST /webhooks/payment - Process payment events
- GET /health - System health check
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db

logger = logging.getLogger(__name__)

async def process_payment_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process a payment event and trigger service delivery."""
    try:
        # Validate required fields
        required_fields = ["payment_id", "amount", "currency", "status", "customer_id"]
        for field in required_fields:
            if field not in event:
                return {"success": False, "error": f"Missing required field: {field}"}

        # Only process successful payments
        if event["status"] != "succeeded":
            return {"success": True, "message": "Payment not successful, skipping"}

        # Record revenue event
        revenue_event = {
            "event_type": "revenue",
            "amount_cents": int(float(event["amount"]) * 100),
            "currency": event["currency"],
            "source": "payment_webhook",
            "metadata": {
                "payment_id": event["payment_id"],
                "customer_id": event["customer_id"]
            },
            "recorded_at": datetime.now(timezone.utc).isoformat()
        }

        # Insert revenue event
        await query_db(f"""
            INSERT INTO revenue_events (id, event_type, amount_cents, currency, source, metadata, recorded_at)
            VALUES (gen_random_uuid(), 'revenue', {revenue_event['amount_cents']}, 
                    '{revenue_event['currency']}', '{revenue_event['source']}', 
                    '{json.dumps(revenue_event['metadata'])}'::jsonb, 
                    '{revenue_event['recorded_at']}')
        """)

        # TODO: Trigger service delivery automation
        # await deliver_service(event)

        return {"success": True, "message": "Payment processed successfully"}

    except Exception as e:
        logger.error(f"Failed to process payment: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

async def health_check() -> Dict[str, Any]:
    """Perform system health check."""
    try:
        # Check database connectivity
        await query_db("SELECT 1")
        return {"success": True, "status": "healthy"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

async def handle_payment_webhook(body: str) -> Dict[str, Any]:
    """Handle incoming payment webhook."""
    try:
        event = json.loads(body)
        return await process_payment_event(event)
    except json.JSONDecodeError:
        return {"success": False, "error": "Invalid JSON payload"}
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

def route_webhook_request(path: str, method: str, body: Optional[str] = None) -> Dict[str, Any]:
    """Route webhook API requests."""
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # POST /webhooks/payment
    if len(parts) == 2 and parts[0] == "webhooks" and parts[1] == "payment" and method == "POST":
        return handle_payment_webhook(body)
    
    # GET /health
    if len(parts) == 1 and parts[0] == "health" and method == "GET":
        return health_check()
    
    return {"success": False, "error": "Not found"}

__all__ = ["route_webhook_request"]
