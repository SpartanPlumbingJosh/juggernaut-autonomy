from __future__ import annotations
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
import stripe
from tenacity import retry, stop_after_attempt, wait_exponential

class PaymentProcessor:
    """Autonomous payment processing with retries and self-healing."""
    
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.logger = logging.getLogger(__name__)
        self.health_status = "healthy"
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def create_payment_intent(
        self, 
        amount: float, 
        currency: str = "usd",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Create payment intent with automatic retries."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True}
            )
            self.health_status = "healthy"
            return True, intent
        except stripe.error.StripeError as e:
            self.logger.error(f"Payment failed: {str(e)}")
            self.health_status = "degraded"
            return False, None
            
    async def handle_webhook(self, payload: str, sig_header: str, endpoint_secret: str) -> Dict[str, Any]:
        """Process Stripe webhook events for payment status."""
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
            
            if event['type'] == 'payment_intent.succeeded':
                intent = event['data']['object']
                return {"success": True, "payment_id": intent['id'], "amount": intent['amount']}
                
            elif event['type'] == 'payment_intent.payment_failed':
                intent = event['data']['object']
                error = intent.get('last_payment_error', {})
                return {
                    "success": False,
                    "payment_id": intent['id'],
                    "error": error.get('message', 'unknown error')
                }
                
        except stripe.error.SignatureVerificationError as e:
            self.logger.error(f"Webhook signature verification failed: {str(e)}")
            return {"success": False, "error": "Invalid signature"}
        except stripe.error.StripeError as e:
            self.logger.error(f"Webhook processing error: {str(e)}")
            return {"success": False, "error": str(e)}
