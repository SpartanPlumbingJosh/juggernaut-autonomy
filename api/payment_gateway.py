import os
import json
import hmac
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from core.database import execute_sql
from core.logging import log_action

PAYMENT_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET")

class PaymentGateway:
    """Handle payment processing and webhook verification."""
    
    @staticmethod
    async def verify_webhook(payload: bytes, signature: str) -> bool:
        """Verify webhook signature."""
        if not PAYMENT_SECRET:
            return False
            
        expected = hmac.new(
            PAYMENT_SECRET.encode(),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)

    @staticmethod
    async def process_payment(event: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Process payment event and fulfill order."""
        try:
            payment_id = event.get("id")
            amount = event.get("amount") / 100  # Convert cents to dollars
            customer = event.get("customer", {})
            metadata = event.get("metadata", {})
            
            # Record payment in database
            await execute_sql(
                f"""
                INSERT INTO payments (
                    payment_id, amount, currency, status,
                    customer_email, customer_id, payment_method,
                    created_at, metadata
                ) VALUES (
                    '{payment_id}', {amount}, '{event.get("currency", "usd")}',
                    '{event.get("status", "pending")}', 
                    '{customer.get("email", "")}',
                    '{customer.get("id", "")}',
                    '{event.get("payment_method", "")}',
                    NOW(),
                    '{json.dumps(metadata)}'::jsonb
                )
                """
            )
            
            # Trigger fulfillment
            fulfillment_success = await FulfillmentService.process_order(
                payment_id=payment_id,
                customer=customer,
                items=metadata.get("items", []),
                amount=amount
            )
            
            if not fulfillment_success:
                raise Exception("Fulfillment failed")
                
            return True, None
            
        except Exception as e:
            log_action(
                "payment.failed",
                f"Payment processing failed: {str(e)}",
                level="error",
                error_data={"error": str(e), "event": event}
            )
            return False, str(e)

    @staticmethod
    async def handle_webhook(payload: bytes, signature: str) -> Dict[str, Any]:
        """Handle payment webhook."""
        try:
            if not await PaymentGateway.verify_webhook(payload, signature):
                return {"status": "error", "message": "Invalid signature"}
                
            event = json.loads(payload.decode())
            event_type = event.get("type")
            
            if event_type == "payment.succeeded":
                success, error = await PaymentGateway.process_payment(event)
                if not success:
                    return {"status": "error", "message": error}
                    
            return {"status": "success"}
            
        except Exception as e:
            log_action(
                "payment.webhook_error",
                f"Webhook processing failed: {str(e)}",
                level="error",
                error_data={"error": str(e)}
            )
            return {"status": "error", "message": str(e)}
