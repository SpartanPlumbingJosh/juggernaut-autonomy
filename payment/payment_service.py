import os
import stripe
from typing import Optional, Dict, Any
from datetime import datetime

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class PaymentService:
    def __init__(self):
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    def create_customer(self, email: str, name: str) -> Dict[str, Any]:
        """Create a new Stripe customer"""
        return stripe.Customer.create(
            email=email,
            name=name,
            description=f"Customer created on {datetime.utcnow().isoformat()}"
        )

    def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create a new subscription"""
        return stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            expand=["latest_invoice.payment_intent"]
        )

    def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Handle Stripe webhook events"""
        event = stripe.Webhook.construct_event(
            payload, sig_header, self.webhook_secret
        )
        
        # Handle different event types
        if event['type'] == 'payment_intent.succeeded':
            return self._handle_payment_success(event)
        elif event['type'] == 'invoice.payment_failed':
            return self._handle_payment_failure(event)
        elif event['type'] == 'customer.subscription.deleted':
            return self._handle_subscription_cancelled(event)
        
        return {"status": "unhandled_event"}

    def _handle_payment_success(self, event: Dict[str, Any]) -> Dict[str, Any]:
        # Handle successful payment
        return {"status": "success"}

    def _handle_payment_failure(self, event: Dict[str, Any]) -> Dict[str, Any]:
        # Handle payment failure
        return {"status": "failure"}

    def _handle_subscription_cancelled(self, event: Dict[str, Any]) -> Dict[str, Any]:
        # Handle subscription cancellation
        return {"status": "cancelled"}
