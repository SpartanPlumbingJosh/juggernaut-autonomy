import stripe
import json
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    """Handle payment processing through supported gateways."""
    
    def __init__(self, stripe_api_key: str):
        self.stripe = stripe
        self.stripe.api_key = stripe_api_key

    async def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a customer in payment processor."""
        customer = self.stripe.Customer.create(
            email=email,
            name=name,
            metadata=metadata or {}
        )
        return {
            "id": customer.id,
            "payment_methods": [],
            "created": datetime.fromtimestamp(customer.created)
        }

    async def create_payment_intent(
        self,
        amount_cents: int,
        currency: str,
        customer_id: str,
        description: str,
        metadata: Dict
    ) -> Dict:
        """Create a payment intent for one-time charges."""
        intent = self.stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            customer=customer_id,
            description=description,
            metadata=metadata
        )
        return {
            "id": intent.id,
            "client_secret": intent.client_secret,
            "status": intent.status
        }

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Dict
    ) -> Dict:
        """Create a subscription in payment processor."""
        subscription = self.stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            metadata=metadata
        )
        return {
            "id": subscription.id,
            "status": subscription.status,
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end)
        }
