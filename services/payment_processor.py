import stripe
from typing import Dict, Optional
import logging

from core.config import settings

log = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self):
        self.stripe_api_key = settings.STRIPE_SECRET_KEY
        stripe.api_key = self.stripe_api_key

    async def create_payment_intent(
        self,
        amount_cents: int,
        currency: str = "usd",
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create a Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True},
            )
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id
            }
        except Exception as e:
            log.error(f"Payment intent failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def capture_payment(
        self,
        payment_intent_id: str,
        amount_cents: int
    ) -> Dict:
        """Capture and validate a payment."""
        try:
            intent = stripe.PaymentIntent.capture(payment_intent_id)
            if intent.status == "succeeded" and intent.amount_received == amount_cents:
                return {
                    "success": True,
                    "payment_intent_id": intent.id,
                    "amount_cents": intent.amount_received,
                    "currency": intent.currency
                }
            else:
                return {"success": False, "error": f"Payment failed with status: {intent.status}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def refund_payment(
        self,
        payment_intent_id: str,
        amount_cents: Optional[int] = None
    ) -> Dict:
        """Issue a full or partial refund."""
        try:
            kwargs = {}
            if amount_cents:
                kwargs["amount"] = amount_cents
                
            refund = stripe.Refund.create(
                payment_intent=payment_intent_id,
                **kwargs
            )
            return {
                "success": True,
                "refund_id": refund.id,
                "amount_cents": kwargs.get("amount") if kwargs else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
