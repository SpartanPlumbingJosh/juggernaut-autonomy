import stripe
from typing import Dict, Optional
from datetime import datetime
from core.database import query_db

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.stripe = stripe

    async def create_customer(self, email: str, name: str) -> Dict:
        """Create a new Stripe customer"""
        try:
            customer = self.stripe.Customer.create(
                email=email,
                name=name,
                description=f"Customer created on {datetime.now().isoformat()}"
            )
            return {"success": True, "customer": customer}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_payment_intent(self, amount: int, currency: str, customer_id: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent for a customer"""
        try:
            intent = self.stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True}
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def record_transaction(self, event_data: Dict) -> Dict:
        """Record a successful transaction in our database"""
        try:
            amount = event_data.get("amount")
            currency = event_data.get("currency")
            customer_id = event_data.get("customer")
            payment_intent_id = event_data.get("id")
            
            sql = f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount},
                '{currency}',
                'stripe',
                '{json.dumps(event_data)}'::jsonb,
                NOW(),
                NOW()
            )
            """
            await query_db(sql)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
