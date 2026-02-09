import stripe
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.logger = logging.getLogger(__name__)

    def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new customer in Stripe."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return customer
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to create customer: {str(e)}")
            raise

    def create_subscription(self, customer_id: str, price_id: str, trial_days: int = 0) -> Dict:
        """Create a new subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                trial_period_days=trial_days
            )
            return subscription
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to create subscription: {str(e)}")
            raise

    def create_payment_intent(self, amount: int, currency: str, customer_id: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent for one-time charges."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True}
            )
            return intent
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to create payment intent: {str(e)}")
            raise

    def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                self._handle_payment_success(event['data']['object'])
            elif event['type'] == 'invoice.payment_succeeded':
                self._handle_invoice_payment(event['data']['object'])
            elif event['type'] == 'customer.subscription.deleted':
                self._handle_subscription_cancelled(event['data']['object'])
            
            return {"status": "success"}
        except stripe.error.SignatureVerificationError as e:
            self.logger.error(f"Webhook signature verification failed: {str(e)}")
            raise
        except stripe.error.StripeError as e:
            self.logger.error(f"Webhook processing failed: {str(e)}")
            raise

    def _handle_payment_success(self, payment_intent: Dict) -> None:
        """Handle successful payment."""
        # Log payment and trigger service delivery
        self.logger.info(f"Payment succeeded: {payment_intent['id']}")
        # TODO: Trigger service delivery workflow

    def _handle_invoice_payment(self, invoice: Dict) -> None:
        """Handle successful subscription payment."""
        self.logger.info(f"Subscription payment succeeded: {invoice['id']}")
        # TODO: Update subscription status

    def _handle_subscription_cancelled(self, subscription: Dict) -> None:
        """Handle subscription cancellation."""
        self.logger.info(f"Subscription cancelled: {subscription['id']}")
        # TODO: Update access and notify customer

    def generate_invoice_pdf(self, invoice_id: str) -> bytes:
        """Generate PDF for an invoice."""
        try:
            invoice = stripe.Invoice.retrieve(invoice_id)
            pdf = stripe.Invoice.pdf(invoice_id)
            return pdf
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to generate invoice PDF: {str(e)}")
            raise
