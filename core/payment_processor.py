import stripe
from typing import Dict, Optional
from datetime import datetime
from core.database import execute_sql

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.stripe = stripe

    async def create_customer(self, email: str, name: str) -> Dict:
        """Create a new Stripe customer."""
        try:
            customer = self.stripe.Customer.create(
                email=email,
                name=name,
                description=f"Customer created on {datetime.utcnow().isoformat()}"
            )
            return {"success": True, "customer": customer}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_payment_intent(self, amount_cents: int, currency: str, customer_id: str) -> Dict:
        """Create a payment intent for a customer."""
        try:
            intent = self.stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                customer=customer_id,
                automatic_payment_methods={"enabled": True},
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def record_transaction(self, payment_intent_id: str) -> Dict:
        """Record a successful transaction in our database."""
        try:
            intent = self.stripe.PaymentIntent.retrieve(payment_intent_id)
            
            await execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {intent.amount},
                    '{intent.currency}',
                    'stripe',
                    '{json.dumps({
                        "payment_intent": intent.id,
                        "customer": intent.customer,
                        "payment_method": intent.payment_method
                    })}',
                    NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )

            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                await self.record_transaction(payment_intent['id'])

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
