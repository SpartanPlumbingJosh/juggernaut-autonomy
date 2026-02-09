import os
import stripe
from datetime import datetime
from typing import Dict, Optional

class StripePaymentService:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    async def create_payment_intent(self, amount: int, currency: str, metadata: Dict) -> Dict:
        """Create a Stripe PaymentIntent"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency.lower(),
                automatic_payment_methods={"enabled": True},
                metadata=metadata
            )
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                intent = event['data']['object']
                metadata = intent.get('metadata', {})
                
                if not metadata.get('processed'):
                    # Process successful payment logic here
                    pass
                    
            return {"success": True, "event": event.type}
            
        except ValueError as e:
            return {"success": False, "error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            return {"success": False, "error": "Invalid signature"}
