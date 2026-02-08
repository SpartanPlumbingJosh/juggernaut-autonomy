import hmac
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from core.database import query_db, execute_db
from core.logging import log_action
from core.fraud import FraudDetector

WEBHOOK_SECRET = "your_webhook_secret"  # Should be from env vars
MAX_RETRIES = 3
RETRY_DELAY = 60  # seconds

class PaymentWebhook:
    def __init__(self):
        self.fraud_detector = FraudDetector()

    async def verify_signature(self, request: Request, body: bytes) -> bool:
        """Verify webhook signature for security."""
        signature = request.headers.get("X-Signature")
        if not signature:
            return False
            
        expected = hmac.new(
            WEBHOOK_SECRET.encode(),
            msg=body,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)

    async def handle_payment_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment webhook event."""
        event_type = event.get("type")
        data = event.get("data", {})
        
        # Fraud check
        fraud_score = await self.fraud_detector.analyze_event(event)
        if fraud_score > 0.8:
            return {"status": "fraud_detected", "score": fraud_score}
            
        # Handle different event types
        if event_type == "payment.success":
            return await self.handle_successful_payment(data)
        elif event_type == "payment.failed":
            return await self.handle_failed_payment(data)
        elif event_type == "refund.created":
            return await self.handle_refund(data)
            
        return {"status": "unhandled_event_type"}

    async def handle_successful_payment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process successful payment."""
        payment_id = data.get("id")
        amount = data.get("amount")
        currency = data.get("currency")
        customer = data.get("customer")
        
        # Record payment
        await execute_db(
            f"""
            INSERT INTO payments (
                id, status, amount, currency, customer_id,
                created_at, updated_at, metadata
            ) VALUES (
                '{payment_id}', 'success', {amount}, '{currency}',
                '{customer.get("id")}', NOW(), NOW(),
                '{json.dumps(data)}'::jsonb
            )
            """
        )
        
        # Provision user access
        await self.provision_access(customer)
        
        # Generate receipt
        await self.generate_receipt(payment_id)
        
        return {"status": "success"}

    async def handle_failed_payment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process failed payment with retry logic."""
        payment_id = data.get("id")
        retry_count = data.get("retry_count", 0)
        
        if retry_count < MAX_RETRIES:
            # Schedule retry
            await self.schedule_retry(payment_id, retry_count + 1)
            return {"status": "retry_scheduled"}
            
        # Mark as failed
        await execute_db(
            f"""
            UPDATE payments
            SET status = 'failed',
                updated_at = NOW()
            WHERE id = '{payment_id}'
            """
        )
        return {"status": "failed"}

    async def provision_access(self, customer: Dict[str, Any]) -> None:
        """Provision user access based on payment."""
        # Implementation depends on your service
        pass

    async def generate_receipt(self, payment_id: str) -> None:
        """Generate and send receipt."""
        # Implementation depends on your receipt system
        pass

    async def schedule_retry(self, payment_id: str, retry_count: int) -> None:
        """Schedule payment retry."""
        # Implementation depends on your retry system
        pass

async def payment_webhook(request: Request) -> JSONResponse:
    """Handle incoming payment webhooks."""
    body = await request.body()
    webhook = PaymentWebhook()
    
    if not await webhook.verify_signature(request, body):
        raise HTTPException(status_code=401, detail="Invalid signature")
        
    try:
        event = json.loads(body)
        result = await webhook.handle_payment_event(event)
        return JSONResponse(result)
    except Exception as e:
        log_action("payment.webhook_error", str(e), level="error")
        raise HTTPException(status_code=500, detail=str(e))
