import stripe
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    def create_customer(self, email: str, name: str) -> Dict:
        """Create a new customer in Stripe"""
        return stripe.Customer.create(
            email=email,
            name=name,
            description=f"Customer created on {datetime.utcnow().isoformat()}"
        )
        
    def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a subscription for a customer"""
        return stripe.Subscription.create(
            customer=customer_id,
            items=[{
                'price': price_id,
            }],
            expand=['latest_invoice.payment_intent']
        )
        
    def create_payment_intent(self, amount: int, currency: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent for one-time payments"""
        return stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            metadata=metadata or {}
        )
