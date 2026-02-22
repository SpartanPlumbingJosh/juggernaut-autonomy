import stripe
from typing import Dict, Optional
from datetime import datetime
from core.database import query_db, execute_db

class PaymentGateway:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    def create_customer(self, email: str, name: str) -> Dict:
        """Create a new Stripe customer"""
        return stripe.Customer.create(
            email=email,
            name=name,
            description=f"Customer created on {datetime.utcnow().isoformat()}"
        )
        
    def create_payment_method(self, card_details: Dict) -> Dict:
        """Create a payment method from card details"""
        return stripe.PaymentMethod.create(
            type="card",
            card=card_details
        )
        
    def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a new subscription"""
        return stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            expand=["latest_invoice.payment_intent"]
        )
        
    def process_payment(self, amount: int, currency: str, payment_method_id: str) -> Dict:
        """Process a payment"""
        return stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            payment_method=payment_method_id,
            confirm=True,
            off_session=True
        )
        
    def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict:
        """Handle Stripe webhook events"""
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        
        # Handle specific event types
        if event['type'] == 'payment_intent.succeeded':
            self._handle_payment_success(event['data']['object'])
        elif event['type'] == 'invoice.payment_failed':
            self._handle_payment_failure(event['data']['object'])
            
        return {"success": True}
        
    def _handle_payment_success(self, payment_intent: Dict) -> None:
        """Handle successful payment"""
        execute_db(
            f"""
            INSERT INTO payments (
                id, customer_id, amount, currency, status,
                payment_method, created_at, updated_at
            ) VALUES (
                '{payment_intent['id']}',
                '{payment_intent['customer']}',
                {payment_intent['amount']},
                '{payment_intent['currency']}',
                'succeeded',
                '{payment_intent['payment_method']}',
                NOW(),
                NOW()
            )
            """
        )
        
    def _handle_payment_failure(self, invoice: Dict) -> None:
        """Handle payment failure"""
        execute_db(
            f"""
            UPDATE subscriptions
            SET status = 'past_due',
                updated_at = NOW()
            WHERE stripe_id = '{invoice['subscription']}'
            """
        )
