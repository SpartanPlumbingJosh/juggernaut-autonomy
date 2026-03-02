import stripe
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class StripeClient:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.stripe = stripe

    def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new Stripe customer"""
        try:
            return self.stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            raise

    def create_subscription(self, customer_id: str, price_id: str, trial_days: int = 0) -> Dict:
        """Create a new subscription"""
        try:
            return self.stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                trial_period_days=trial_days,
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            raise

    def cancel_subscription(self, subscription_id: str) -> Dict:
        """Cancel a subscription"""
        try:
            return self.stripe.Subscription.delete(subscription_id)
        except Exception as e:
            logger.error(f"Failed to cancel subscription: {str(e)}")
            raise

    def create_invoice(self, customer_id: str, amount: int, currency: str = "usd") -> Dict:
        """Create an invoice for a customer"""
        try:
            return self.stripe.Invoice.create(
                customer=customer_id,
                amount=amount,
                currency=currency,
                auto_advance=True
            )
        except Exception as e:
            logger.error(f"Failed to create invoice: {str(e)}")
            raise

    def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict:
        """Handle Stripe webhook events"""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            return self._process_event(event)
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            raise

    def _process_event(self, event: Dict) -> Dict:
        """Process Stripe webhook event"""
        event_type = event['type']
        data = event['data']
        
        handlers = {
            'invoice.payment_succeeded': self._handle_payment_success,
            'invoice.payment_failed': self._handle_payment_failure,
            'customer.subscription.deleted': self._handle_subscription_cancelled,
            'customer.subscription.updated': self._handle_subscription_updated,
        }

        handler = handlers.get(event_type)
        if handler:
            return handler(data)
        return {"status": "unhandled_event"}

    def _handle_payment_success(self, data: Dict) -> Dict:
        """Handle successful payment"""
        invoice = data['object']
        # Update your system with successful payment
        return {"status": "success"}

    def _handle_payment_failure(self, data: Dict) -> Dict:
        """Handle failed payment"""
        invoice = data['object']
        # Trigger dunning process
        return {"status": "failure_handled"}

    def _handle_subscription_cancelled(self, data: Dict) -> Dict:
        """Handle subscription cancellation"""
        subscription = data['object']
        # Update your system with cancellation
        return {"status": "cancellation_handled"}

    def _handle_subscription_updated(self, data: Dict) -> Dict:
        """Handle subscription changes"""
        subscription = data['object']
        # Update your system with changes
        return {"status": "update_handled"}
