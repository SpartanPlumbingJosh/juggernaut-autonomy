import os
import stripe
from typing import Dict, Any

class PaymentProcessor:
    """Handle payment processing operations."""
    
    def __init__(self):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    async def create_payment_intent(self, amount_cents: int, currency: str, metadata: Dict[str, Any]):
        """Create a Stripe payment intent."""
        return stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            metadata=metadata,
            automatic_payment_methods={"enabled": True},
        )
    
    async def handle_webhook(self, payload: str, sig_header: str):
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                # Handle successful payment
                return {"success": True, "payment_intent_id": payment_intent['id']}
            
            return {"success": False, "error": "Unhandled event type"}
        except Exception as e:
            return {"success": False, "error": str(e)}
