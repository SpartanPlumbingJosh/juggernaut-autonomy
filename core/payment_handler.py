import stripe
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.database import query_db

class PaymentHandler:
    def __init__(self, stripe_secret_key: str):
        stripe.api_key = stripe_secret_key
        
    async def create_payment_intent(self, amount_cents: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata,
                payment_method_types=['card'],
            )
            return {"success": True, "client_secret": intent.client_secret}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """Handle Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                await self._record_payment(payment_intent)
                
            return {"success": True}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def _record_payment(self, payment_intent: Dict[str, Any]) -> None:
        """Record successful payment in revenue events."""
        metadata = payment_intent.get('metadata', {})
        amount_cents = payment_intent.get('amount')
        currency = payment_intent.get('currency')
        
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                '{currency}',
                'stripe',
                '{json.dumps(metadata)}',
                NOW(),
                NOW()
            )
        """)
