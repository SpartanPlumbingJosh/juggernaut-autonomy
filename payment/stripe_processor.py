import stripe
from typing import Dict, Any
from datetime import datetime

class StripeProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    def create_payment_intent(self, amount_cents: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payment intent with Stripe"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata
            )
            return {
                "success": True,
                "payment_intent_id": intent.id,
                "client_secret": intent.client_secret,
                "status": intent.status
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def capture_payment(self, payment_intent_id: str) -> Dict[str, Any]:
        """Capture a payment"""
        try:
            intent = stripe.PaymentIntent.capture(payment_intent_id)
            return {
                "success": True,
                "amount_captured": intent.amount_received,
                "currency": intent.currency,
                "status": intent.status
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def create_refund(self, payment_intent_id: str, amount_cents: int) -> Dict[str, Any]:
        """Create a refund"""
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_intent_id,
                amount=amount_cents
            )
            return {
                "success": True,
                "refund_id": refund.id,
                "amount": refund.amount,
                "status": refund.status
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
