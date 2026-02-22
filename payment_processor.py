"""
Basic payment processing - Stripe integration for MVP
"""
import stripe
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.client = stripe
    
    def create_customer(self, email: str, name: str) -> Dict:
        """Create a new customer record"""
        return self.client.Customer.create(
            email=email,
            name=name,
            metadata={"created_at": datetime.utcnow().isoformat()}
        )
    
    def create_payment_intent(
        self, 
        amount_cents: int,
        currency: str = "usd",
        customer_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create payment intent for immediate charge"""
        return self.client.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            customer=customer_id,
            metadata=metadata or {},
            payment_method_types=["card"],
            confirm=True
        )
    
    def create_subscription(
        self, 
        price_id: str,
        customer_id: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create recurring subscription"""
        return self.client.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            metadata=metadata or {},
            expand=["latest_invoice.payment_intent"]
        )
