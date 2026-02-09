import stripe
from typing import Dict, Optional
from core.database import query_db

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
                description="Automated revenue stream customer"
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_payment_intent(self, amount: int, currency: str, customer_id: str, 
                                  metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent for immediate charge."""
        try:
            intent = self.stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                automatic_payment_methods={"enabled": True},
                metadata=metadata or {}
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def record_payment_event(self, event_data: Dict) -> Dict:
        """Record payment event in our database."""
        try:
            amount_cents = event_data.get("amount", 0)
            await query_db(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, 
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {amount_cents},
                    '{event_data.get("currency", "usd")}',
                    'stripe',
                    '{json.dumps(event_data)}',
                    NOW(),
                    NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
