import stripe
import logging
from typing import Dict, Optional
from datetime import datetime, timezone

class StripeProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.logger = logging.getLogger(__name__)
        
    async def create_payment_intent(self, amount_cents: int, currency: str, metadata: Dict) -> Optional[Dict]:
        """Create a payment intent with Stripe"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata,
                automatic_payment_methods={"enabled": True}
            )
            return {
                "id": intent.id,
                "client_secret": intent.client_secret,
                "status": intent.status
            }
        except Exception as e:
            self.logger.error(f"Failed to create payment intent: {str(e)}")
            return None
            
    async def handle_webhook(self, payload: bytes, sig_header: str, webhook_secret: str) -> Dict:
        """Process Stripe webhook event"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event.type == "payment_intent.succeeded":
                payment_intent = event.data.object
                return self._process_successful_payment(payment_intent)
                
            elif event.type == "payment_intent.payment_failed":
                payment_intent = event.data.object
                return self._process_failed_payment(payment_intent)
                
            return {"status": "unhandled_event"}
            
        except Exception as e:
            self.logger.error(f"Webhook processing failed: {str(e)}")
            return {"status": "error", "error": str(e)}
            
    def _process_successful_payment(self, payment_intent) -> Dict:
        """Handle successful payment"""
        metadata = payment_intent.metadata
        amount_cents = payment_intent.amount
        currency = payment_intent.currency
        
        return {
            "status": "success",
            "payment_id": payment_intent.id,
            "amount_cents": amount_cents,
            "currency": currency,
            "metadata": metadata,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    def _process_failed_payment(self, payment_intent) -> Dict:
        """Handle failed payment"""
        return {
            "status": "failed",
            "payment_id": payment_intent.id,
            "error": payment_intent.last_payment_error or "unknown",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
