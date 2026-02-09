import stripe
from typing import Dict, Optional
from datetime import datetime
from core.database import query_db

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    async def create_customer(self, email: str, name: str) -> Dict:
        """Create a Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                description=f"Customer created on {datetime.utcnow().isoformat()}"
            )
            return {"success": True, "customer": customer}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def create_payment_intent(self, amount: int, currency: str, customer_id: str) -> Dict:
        """Create a payment intent"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                automatic_payment_methods={"enabled": True},
            )
            return {"success": True, "client_secret": intent.client_secret}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def handle_webhook(self, payload: bytes, sig_header: str, webhook_secret: str) -> Dict:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                await self._handle_successful_payment(payment_intent)
                
            return {"success": True}
        except ValueError as e:
            return {"success": False, "error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            return {"success": False, "error": "Invalid signature"}
            
    async def _handle_successful_payment(self, payment_intent: Dict) -> None:
        """Handle successful payment"""
        await query_db(f"""
            INSERT INTO transactions (id, amount, currency, customer_id, status, created_at)
            VALUES (
                '{payment_intent['id']}',
                {payment_intent['amount']},
                '{payment_intent['currency']}',
                '{payment_intent['customer']}',
                'completed',
                NOW()
            )
        """)
