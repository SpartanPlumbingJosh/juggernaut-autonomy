import stripe
from typing import Dict, Optional
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

class StripeService:
    def __init__(self):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    def create_customer(self, email: str, name: str) -> Optional[Dict]:
        try:
            return stripe.Customer.create(
                email=email,
                name=name,
                description=f"Customer created on {datetime.utcnow().isoformat()}"
            )
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return None

    def create_payment_intent(self, amount: int, currency: str, customer_id: str) -> Optional[Dict]:
        try:
            return stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                automatic_payment_methods={"enabled": True},
            )
        except Exception as e:
            logger.error(f"Failed to create payment intent: {str(e)}")
            return None

    def handle_webhook(self, payload: str, sig_header: str) -> Optional[Dict]:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return event
        except ValueError as e:
            logger.error(f"Invalid payload: {str(e)}")
            return None
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {str(e)}")
            return None
