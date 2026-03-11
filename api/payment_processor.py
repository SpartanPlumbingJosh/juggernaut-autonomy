"""
Payment Processor - Handle customer payments and subscriptions.

Supports:
- Stripe integration
- Payment intents
- Subscription management
- Webhook handling
"""

import os
import stripe
from datetime import datetime
from typing import Dict, Optional

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class PaymentProcessor:
    def __init__(self):
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    def create_payment_intent(self, amount: int, currency: str = "usd", metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent for immediate payment."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata or {},
                payment_method_types=["card"]
            )
            return {
                "client_secret": intent.client_secret,
                "id": intent.id,
                "status": intent.status
            }
        except Exception as e:
            return {"error": str(e)}

    def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a recurring subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "id": subscription.id,
                "status": subscription.status,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret
            }
        except Exception as e:
            return {"error": str(e)}

    def handle_webhook(self, payload: str, sig_header: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event["type"] == "payment_intent.succeeded":
                self._handle_payment_success(event["data"]["object"])
            elif event["type"] == "invoice.payment_succeeded":
                self._handle_subscription_payment(event["data"]["object"])
            
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    def _handle_payment_success(self, payment_intent: Dict) -> None:
        """Handle successful one-time payment."""
        # Record transaction in revenue_events
        pass

    def _handle_subscription_payment(self, invoice: Dict) -> None:
        """Handle successful subscription payment."""
        # Record recurring revenue in revenue_events
        pass
