import os
import stripe
from typing import Dict, Optional

class PaymentGateway:
    def __init__(self):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    def create_customer(self, email: str, name: str) -> Dict:
        """Create a new customer in Stripe."""
        return stripe.Customer.create(
            email=email,
            name=name,
            description="Automated customer creation"
        )

    def create_payment_intent(self, amount: int, currency: str, customer_id: str) -> Dict:
        """Create a payment intent for a customer."""
        return stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            customer=customer_id,
            automatic_payment_methods={"enabled": True},
        )

    def handle_webhook(self, payload: str, sig_header: str) -> Optional[Dict]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return event
        except Exception as e:
            return None
