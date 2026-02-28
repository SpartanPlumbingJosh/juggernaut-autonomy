import stripe
import os
from datetime import datetime
from typing import Dict, Optional

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class PaymentProcessor:
    """Handles payment processing via Stripe"""
    
    def __init__(self):
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    async def create_payment_intent(self, amount: int, currency: str = "usd", metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True},
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event["type"] == "payment_intent.succeeded":
                payment_intent = event["data"]["object"]
                await self._handle_successful_payment(payment_intent)
                
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _handle_successful_payment(self, payment_intent: Dict) -> None:
        """Handle successful payment"""
        # Record transaction in revenue_events
        metadata = payment_intent.get("metadata", {})
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {payment_intent["amount"]},
                '{payment_intent["currency"]}',
                'stripe',
                '{json.dumps(metadata)}',
                NOW(),
                NOW()
            )
        """)
