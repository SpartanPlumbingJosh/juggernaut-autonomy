import os
import stripe
from typing import Dict, Optional

class PaymentProcessor:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    def create_customer(self, email: str, name: str) -> Dict:
        """Create a new Stripe customer."""
        return stripe.Customer.create(
            email=email,
            name=name,
            description="Created via MVP"
        )

    def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a new subscription."""
        return stripe.Subscription.create(
            customer=customer_id,
            items=[{
                'price': price_id,
            }],
            payment_behavior='default_incomplete',
            expand=['latest_invoice.payment_intent']
        )

    def handle_webhook(self, payload: str, sig_header: str) -> Optional[Dict]:
        """Handle Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return event
        except Exception as e:
            return None

    def get_payment_intent(self, payment_intent_id: str) -> Dict:
        """Retrieve payment intent details."""
        return stripe.PaymentIntent.retrieve(payment_intent_id)

    def cancel_subscription(self, subscription_id: str) -> Dict:
        """Cancel a subscription."""
        return stripe.Subscription.delete(subscription_id)
