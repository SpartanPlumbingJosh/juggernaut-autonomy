import stripe
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.stripe = stripe

    async def create_customer(self, email: str, name: str) -> Dict[str, Any]:
        """Create a new Stripe customer."""
        try:
            customer = self.stripe.Customer.create(
                email=email,
                name=name,
                description=f"Customer created on {datetime.utcnow().isoformat()}"
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_payment_intent(self, amount: int, currency: str, customer_id: str) -> Dict[str, Any]:
        """Create a payment intent for a customer."""
        try:
            intent = self.stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                automatic_payment_methods={"enabled": True},
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            logger.error(f"Failed to create payment intent: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """Handle Stripe webhook events."""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                return await self._handle_successful_payment(payment_intent)
                
            return {"success": True, "event": event['type']}
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _handle_successful_payment(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Process successful payment."""
        # Record revenue event and trigger service delivery
        return {"success": True, "payment_id": payment_intent['id']}
