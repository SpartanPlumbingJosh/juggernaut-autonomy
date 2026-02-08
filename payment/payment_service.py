import stripe
import os
from typing import Dict, Optional

class PaymentService:
    def __init__(self):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    def create_payment_intent(self, amount: int, currency: str = "usd", metadata: Optional[Dict] = None) -> Dict:
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata or {}
            )
            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id
            }
        except Exception as e:
            raise Exception(f"Payment creation failed: {str(e)}")

    def handle_webhook(self, payload: str, sig_header: str) -> Dict:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                return {
                    "status": "success",
                    "payment_intent_id": payment_intent['id'],
                    "amount": payment_intent['amount'],
                    "metadata": payment_intent.get('metadata', {})
                }
            return {"status": "unhandled_event"}
        except Exception as e:
            raise Exception(f"Webhook handling failed: {str(e)}")

payment_service = PaymentService()
