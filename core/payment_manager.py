import os
import stripe
import logging
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum

class PaymentType(Enum):
    SUBSCRIPTION = "subscription"
    ONE_TIME = "one_time"
    USAGE_BASED = "usage_based"

class PaymentManager:
    def __init__(self):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        self.logger = logging.getLogger(__name__)

    def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new customer in Stripe."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer_id": customer.id}
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to create customer: {str(e)}")
            return {"success": False, "error": str(e)}

    def create_payment_intent(self, amount: int, currency: str, customer_id: str, 
                            payment_type: PaymentType, metadata: Dict) -> Dict:
        """Create a payment intent for one-time payments."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                metadata={
                    "payment_type": payment_type.value,
                    **metadata
                }
            )
            return {"success": True, "client_secret": intent.client_secret}
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to create payment intent: {str(e)}")
            return {"success": False, "error": str(e)}

    def create_subscription(self, customer_id: str, price_id: str, metadata: Dict) -> Dict:
        """Create a subscription for a customer."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                metadata=metadata
            )
            return {"success": True, "subscription_id": subscription.id}
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}

    def create_invoice(self, customer_id: str, amount: int, currency: str, 
                      description: str, metadata: Dict) -> Dict:
        """Create and send an invoice."""
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                auto_advance=True,
                collection_method="send_invoice",
                days_until_due=7,
                description=description,
                metadata=metadata
            )
            
            invoice_item = stripe.InvoiceItem.create(
                customer=customer_id,
                amount=amount,
                currency=currency,
                description=description,
                invoice=invoice.id
            )
            
            invoice = stripe.Invoice.finalize_invoice(invoice.id)
            stripe.Invoice.send_invoice(invoice.id)
            
            return {"success": True, "invoice_id": invoice.id}
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to create invoice: {str(e)}")
            return {"success": False, "error": str(e)}

    def handle_webhook_event(self, payload: str, sig_header: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
            )
            
            event_type = event['type']
            data = event['data']
            
            if event_type == 'payment_intent.succeeded':
                self._handle_payment_success(data.object)
            elif event_type == 'invoice.payment_succeeded':
                self._handle_invoice_payment(data.object)
            elif event_type == 'customer.subscription.deleted':
                self._handle_subscription_cancelled(data.object)
                
            return {"success": True}
        except stripe.error.StripeError as e:
            self.logger.error(f"Webhook error: {str(e)}")
            return {"success": False, "error": str(e)}

    def _handle_payment_success(self, payment_intent):
        """Handle successful payment."""
        # Implement your business logic here
        pass

    def _handle_invoice_payment(self, invoice):
        """Handle successful invoice payment."""
        # Implement your business logic here
        pass

    def _handle_subscription_cancelled(self, subscription):
        """Handle subscription cancellation."""
        # Implement your business logic here
        pass
