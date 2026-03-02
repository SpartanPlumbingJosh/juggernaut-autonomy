import stripe
from typing import Dict, Optional
from fastapi import HTTPException

class StripePaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    async def create_payment_intent(self, amount: int, currency: str = "usd", metadata: Optional[Dict] = None) -> Dict:
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata or {}
            )
            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "status": intent.status
            }
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
    async def handle_webhook(self, payload: bytes, sig_header: str, webhook_secret: str) -> Dict:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                return {
                    "event": "payment_succeeded",
                    "payment_intent_id": payment_intent['id'],
                    "amount": payment_intent['amount'],
                    "metadata": payment_intent.get('metadata', {})
                }
                
            return {"event": event['type']}
        except stripe.error.SignatureVerificationError as e:
            raise HTTPException(status_code=400, detail="Invalid signature")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
