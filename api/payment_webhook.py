"""
Payment webhook handler - Processes payment events and triggers service fulfillment.
"""

import json
from typing import Any, Dict

from api.revenue_api import handle_service_fulfillment


async def handle_payment_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process payment webhook events."""
    try:
        event_type = event.get("type")
        if event_type != "payment.succeeded":
            return {"status": "ignored", "reason": "unhandled_event_type"}
            
        data = event.get("data", {})
        payment_id = data.get("id")
        service_id = data.get("metadata", {}).get("service_id")
        customer_email = data.get("customer_email")
        
        if not all([payment_id, service_id, customer_email]):
            return {"status": "error", "reason": "missing_required_fields"}
            
        # Trigger fulfillment
        fulfillment_body = {
            "payment_id": payment_id,
            "service_id": service_id,
            "customer_email": customer_email
        }
        
        fulfillment_response = await handle_service_fulfillment(fulfillment_body)
        
        if fulfillment_response.get("statusCode", 500) >= 400:
            return {
                "status": "error",
                "reason": "fulfillment_failed",
                "details": fulfillment_response.get("body", {})
            }
            
        return {
            "status": "processed",
            "fulfillment": json.loads(fulfillment_response.get("body", "{}"))
        }
        
    except Exception as e:
        return {
            "status": "error",
            "reason": "processing_failed",
            "error": str(e)
        }
