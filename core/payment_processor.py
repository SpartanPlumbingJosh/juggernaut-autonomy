"""
Payment Processor - Handles payment processing and subscription management.
"""

import json
import stripe
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

class PaymentProcessor:
    def __init__(self, stripe_api_key: str):
        self.stripe = stripe
        self.stripe.api_key = stripe_api_key

    def create_customer(self, email: str, name: str) -> Tuple[Optional[str], Optional[str]]:
        """Create a new customer in Stripe."""
        try:
            customer = self.stripe.Customer.create(
                email=email,
                name=name,
                description=f"Customer created on {datetime.utcnow().isoformat()}"
            )
            return customer.id, None
        except Exception as e:
            return None, str(e)

    def create_subscription(self, customer_id: str, price_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Create a subscription for a customer."""
        try:
            subscription = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            return subscription.id, None
        except Exception as e:
            return None, str(e)

    def handle_webhook(self, payload: bytes, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            event_type = event['type']
            data = event['data']
            
            if event_type == 'payment_intent.succeeded':
                return self._handle_payment_success(data)
            elif event_type == 'payment_intent.payment_failed':
                return self._handle_payment_failure(data)
            elif event_type == 'invoice.payment_succeeded':
                return self._handle_invoice_payment(data)
            elif event_type == 'customer.subscription.deleted':
                return self._handle_subscription_cancelled(data)
            
            return {"status": "unhandled_event"}
        except Exception as e:
            return {"error": str(e)}

    def _handle_payment_success(self, data: Dict) -> Dict:
        """Handle successful payment."""
        payment_intent = data['object']
        # Update database with successful payment
        return {"status": "success", "payment_id": payment_intent['id']}

    def _handle_payment_failure(self, data: Dict) -> Dict:
        """Handle failed payment."""
        payment_intent = data['object']
        # Update database with failed payment
        return {"status": "failed", "payment_id": payment_intent['id']}

    def _handle_invoice_payment(self, data: Dict) -> Dict:
        """Handle successful invoice payment."""
        invoice = data['object']
        # Update database with invoice details
        return {"status": "invoice_paid", "invoice_id": invoice['id']}

    def _handle_subscription_cancelled(self, data: Dict) -> Dict:
        """Handle subscription cancellation."""
        subscription = data['object']
        # Update database with cancellation
        return {"status": "subscription_cancelled", "subscription_id": subscription['id']}
