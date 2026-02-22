import stripe
from typing import Dict, Any
from datetime import datetime, timezone
from core.database import query_db

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    async def create_payment_intent(
        self, 
        amount_cents: int, 
        currency: str,
        metadata: Dict[str, Any],
        customer_id: str = None
    ) -> Dict[str, Any]:
        """Create a Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata,
                customer=customer_id,
                automatic_payment_methods={"enabled": True}
            )
            
            # Log revenue event
            await query_db(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'payment_intent_created',
                    {amount_cents},
                    '{currency}',
                    'stripe',
                    '{json.dumps(metadata)}'::jsonb,
                    NOW(),
                    NOW()
                )
                """
            )
            
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook_event(self, payload: str, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            event_type = event['type']
            
            # Handle successful payment
            if event_type == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                await self._handle_successful_payment(payment_intent)
                
            # Handle payment failed
            elif event_type == 'payment_intent.payment_failed':
                payment_intent = event['data']['object']
                await self._handle_failed_payment(payment_intent)
                
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_successful_payment(self, payment_intent: Dict[str, Any]) -> None:
        """Process a successful payment."""
        amount_cents = payment_intent['amount']
        currency = payment_intent['currency']
        metadata = payment_intent.get('metadata', {})
        
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                '{currency}',
                'stripe',
                '{json.dumps(metadata)}'::jsonb,
                NOW(), 
                NOW()
            )
            """
        )
