from typing import Dict, Optional
import stripe

class PaymentGateway:
    """Handles payment processing integration."""
    
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    def create_payment_intent(self, amount_cents: int, currency: str = "usd", metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata or {},
                capture_method="automatic"
            )
            return {"success": True, "payment_intent": intent}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def capture_payment(self, payment_intent_id: str) -> Dict:
        """Capture an authorized payment."""
        try:
            intent = stripe.PaymentIntent.capture(payment_intent_id)
            return {"success": True, "payment_intent": intent}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def refund_payment(self, payment_intent_id: str, amount_cents: Optional[int] = None) -> Dict:
        """Process a refund."""
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_intent_id,
                amount=amount_cents
            )
            return {"success": True, "refund": refund}
        except Exception as e:
            return {"success": False, "error": str(e)}
