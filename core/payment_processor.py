from datetime import datetime, timezone
from typing import Dict, Any, Optional
import stripe
import logging

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    async def create_payment_intent(self, amount_cents: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payment intent and process payment."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata,
                capture_method='automatic',
                payment_method_types=['card'],
            )
            return {"success": True, "payment_intent": intent}
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def capture_payment(self, payment_intent_id: str) -> Dict[str, Any]:
        """Capture an authorized payment."""
        try:
            intent = stripe.PaymentIntent.capture(payment_intent_id)
            return {"success": True, "payment_intent": intent}
        except Exception as e:
            logger.error(f"Payment capture failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def refund_payment(self, payment_intent_id: str, amount_cents: Optional[int] = None) -> Dict[str, Any]:
        """Process a refund."""
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_intent_id,
                amount=amount_cents
            )
            return {"success": True, "refund": refund}
        except Exception as e:
            logger.error(f"Refund failed: {str(e)}")
            return {"success": False, "error": str(e)}
