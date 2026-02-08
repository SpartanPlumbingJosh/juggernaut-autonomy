import stripe
import json
from datetime import datetime
from typing import Dict, Optional
from core.database import query_db

class PaymentProcessor:
    def __init__(self, stripe_api_key: str):
        stripe.api_key = stripe_api_key

    async def create_payment_intent(self, amount: int, currency: str, user_id: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent with Stripe"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata={
                    "user_id": user_id,
                    **(metadata or {})
                }
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: bytes, sig_header: str, webhook_secret: str) -> Dict:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                await self._record_payment(payment_intent)
                
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _record_payment(self, payment_intent: Dict) -> None:
        """Record successful payment in revenue database"""
        amount_cents = payment_intent['amount']
        user_id = payment_intent['metadata'].get('user_id')
        currency = payment_intent['currency']
        payment_id = payment_intent['id']
        
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(), 'revenue', {amount_cents}, '{currency}',
                'stripe', '{json.dumps({
                    "payment_id": payment_id,
                    "user_id": user_id
                })}', NOW(), NOW()
            )
        """)
