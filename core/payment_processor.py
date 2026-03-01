"""
Payment processing integration with Stripe and PayPal.
Handles payment intents, subscriptions, and webhooks.
"""
import os
import stripe
from typing import Dict, Any, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    def create_payment_intent(self, amount: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payment intent for immediate payment."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata,
                payment_method_types=['card']
            )
            return {"success": True, "client_secret": intent.client_secret}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

    def create_subscription(self, customer_id: str, price_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a recurring subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                metadata=metadata,
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

    def handle_webhook(self, payload: str, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event.type == "payment_intent.succeeded":
                self._handle_payment_success(event.data.object)
            elif event.type == "invoice.payment_succeeded":
                self._handle_subscription_payment(event.data.object)
            elif event.type == "customer.subscription.deleted":
                self._handle_subscription_cancelled(event.data.object)
                
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_payment_success(self, payment_intent: Dict[str, Any]) -> None:
        """Handle successful one-time payment."""
        # Record revenue event
        self._record_revenue_event(
            amount=payment_intent["amount"],
            currency=payment_intent["currency"],
            metadata=payment_intent["metadata"],
            event_type="payment"
        )

    def _handle_subscription_payment(self, invoice: Dict[str, Any]) -> None:
        """Handle successful subscription payment."""
        self._record_revenue_event(
            amount=invoice["amount_paid"],
            currency=invoice["currency"],
            metadata=invoice["metadata"],
            event_type="subscription"
        )

    def _handle_subscription_cancelled(self, subscription: Dict[str, Any]) -> None:
        """Handle subscription cancellation."""
        # Update subscription status in database
        pass

    def _record_revenue_event(self, amount: int, currency: str, metadata: Dict[str, Any], event_type: str) -> None:
        """Record revenue event in database."""
        # Implementation would record to revenue_events table
        pass
