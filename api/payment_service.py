"""
Autonomous Payment Service - Handle payment processing and automated service delivery.

Components:
- POST /payment/intent - Create payment intent
- POST /payment/webhook - Handle payment confirmation webhook
- Automatic fulfillment system
- Revenue tracking integration
"""

import uuid
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import query_db

# Mock payment processor client (replace with real implementation)
class PaymentProcessor:
    @staticmethod
    async def create_intent(amount_cents: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Mock payment intent creation."""
        return {
            "id": f"pi_{uuid.uuid4().hex}",
            "client_secret": f"secret_{uuid.uuid4().hex}",
            "status": "requires_payment_method",
            "amount": amount_cents,
            "currency": currency,
            "metadata": metadata
        }

    @staticmethod
    async def retrieve_intent(payment_intent_id: str) -> Dict[str, Any]:
        """Mock retrieving payment intent."""
        return {
            "id": payment_intent_id,
            "status": "succeeded",  # Mock assumes succeeded for demo
            "amount": 1000,  # Mock amount
            "currency": "usd",
            "metadata": {}
        }

async def create_payment_intent(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create payment intent with idempotency check."""
    try:
        # Validate required parameters
        amount_cents = int(params.get("amount_cents", 0))
        currency = str(params.get("currency", "usd")).lower()
        service_key = str(params.get("service_key", ""))
        idempotency_key = str(params.get("idempotency_key", ""))
        
        if amount_cents <= 0:
            return {"error": "Invalid amount", "code": "invalid_amount"}, 400
            
        if not service_key:
            return {"error": "Missing service_key", "code": "missing_service_key"}, 400
            
        # Check for existing intent with same idempotency key
        if idempotency_key:
            existing = await query_db(
                f"SELECT payment_intent_id FROM payment_intents WHERE idempotency_key = '{idempotency_key}' LIMIT 1"
            )
            if existing.get("rows"):
                intent_id = existing["rows"][0]["payment_intent_id"]
                return {"payment_intent_id": intent_id, "existing": True}, 200

        # Create metadata for tracking
        metadata = {
            "service_key": service_key,
            "internal_ref": str(uuid.uuid4())
        }
        
        # Create payment intent
        intent = await PaymentProcessor.create_intent(
            amount_cents=amount_cents,
            currency=currency,
            metadata=metadata
        )
        
        # Record intent in database
        await query_db(
            f"""
            INSERT INTO payment_intents (
                payment_intent_id, 
                amount_cents, 
                currency, 
                status, 
                service_key,
                idempotency_key,
                metadata,
                created_at
            ) VALUES (
                '{intent["id"]}',
                {amount_cents},
                '{currency}',
                '{intent["status"]}',
                '{service_key}',
                '{idempotency_key}',
                '{json.dumps(metadata)}',
                NOW()
            )
            """
        )
        
        return {
            "payment_intent_id": intent["id"],
            "client_secret": intent["client_secret"],
            "amount": intent["amount"],
            "currency": intent["currency"]
        }, 200
        
    except Exception as e:
        return {"error": str(e), "code": "processing_error"}, 500

async def handle_payment_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process payment confirmation webhook."""
    try:
        event_type = payload.get("type")
        payment_intent = payload.get("data", {}).get("object", {})
        payment_intent_id = payment_intent.get("id")
        
        if not payment_intent_id:
            return {"error": "Missing payment_intent_id"}, 400
            
        if event_type != "payment_intent.succeeded":
            return {"status": "ignored", "event_type": event_type}, 200
            
        # Get full intent details
        intent = await PaymentProcessor.retrieve_intent(payment_intent_id)
        
        # Verify payment is complete
        if intent["status"] != "succeeded":
            return {"status": "not_succeeded"}, 200
            
        # Check if already processed
        processed = await query_db(
            f"SELECT fulfilled FROM payment_intents WHERE payment_intent_id = '{payment_intent_id}'"
        )
        if processed.get("rows") and processed["rows"][0]["fulfilled"]:
            return {"status": "already_fulfilled"}, 200
            
        # Mark as fulfilled
        await query_db(
            f"UPDATE payment_intents SET status = 'succeeded', fulfilled = TRUE, fulfilled_at = NOW() "
            f"WHERE payment_intent_id = '{payment_intent_id}'"
        )
        
        # Record revenue
        metadata = payment_intent.get("metadata", {})
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id,
                event_type,
                amount_cents,
                currency,
                source,
                metadata,
                recorded_at,
                created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {intent["amount"]},
                '{intent["currency"]}',
                'direct_payment',
                '{json.dumps({"payment_intent_id": payment_intent_id, **metadata})}',
                NOW(),
                NOW()
            )
            """
        )
        
        # Trigger service fulfillment (actual implementation would vary by service)
        await fulfill_service(payment_intent_id, metadata.get("service_key"))
        
        return {"status": "fulfilled"}, 200
        
    except Exception as e:
        return {"error": str(e), "code": "webhook_error"}, 500

async def fulfill_service(payment_intent_id: str, service_key: str) -> None:
    """Fulfill the purchased service."""
    # Implementation would vary based on the actual service being sold
    # This is a generic template that would be customized
    
    # Example: Digital service fulfillment
    if service_key == "premium_report":
        await generate_and_deliver_report(payment_intent_id)
    elif service_key == "api_access":
        await provision_api_access(payment_intent_id)
    # etc.
    
    # Record fulfillment
    await query_db(
        f"""
        INSERT INTO service_fulfillments (
            id,
            payment_intent_id,
            service_key,
            status,
            completed_at,
            created_at
        ) VALUES (
            gen_random_uuid(),
            '{payment_intent_id}',
            '{service_key}',
            'completed',
            NOW(),
            NOW()
        )
        """
    )

def route_payment_request(path: str, method: str, params: Dict[str, Any], body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Route payment service requests."""
    # Handle CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": {"Access-Control-Allow-Origin": "*"}}
    
    path_parts = [p for p in path.split("/") if p]
    
    # POST /payment/intent
    if len(path_parts) == 2 and path_parts[0] == "payment" and path_parts[1] == "intent" and method == "POST":
        response, status = create_payment_intent(params or {})
        headers = {"Content-Type": "application/json"}
        if status == 200:
            headers["Access-Control-Allow-Origin"] = "*"
        return {
            "statusCode": status,
            "headers": headers,
            "body": json.dumps(response)
        }
    
    # POST /payment/webhook
    if len(path_parts) == 2 and path_parts[0] == "payment" and path_parts[1] == "webhook" and method == "POST":
        response, status = handle_payment_webhook(body or {})
        return {
            "statusCode": status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response)
        }
    
    return {"statusCode": 404, "body": json.dumps({"error": "Not found"})}


__all__ = ["route_payment_request"]
