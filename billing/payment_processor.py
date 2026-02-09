import os
import logging
from datetime import datetime
from typing import Any, Dict, Optional, List
from enum import Enum, auto

import stripe
from dateutil.relativedelta import relativedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class BillingType(Enum):
    SUBSCRIPTION = auto()
    USAGE_BASED = auto()
    ONE_TIME = auto()

class PaymentProcessor:
    def __init__(self):
        self.webhook_handlers = {
            "invoice.payment_succeeded": self._handle_successful_payment,
            "invoice.payment_failed": self._handle_failed_payment,
            "customer.subscription.deleted": self._handle_subscription_ended
        }

    async def create_customer(self, email: str, name: str, metadata: Dict = None) -> Dict:
        """Create a new Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return customer
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create customer: {e}")
            raise

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        payment_method_id: Optional[str] = None
    ) -> Dict:
        """Create a new subscription"""
        try:
            subscription_params = {
                "customer": customer_id,
                "items": [{"price": price_id}],
                "expand": ["latest_invoice.payment_intent"]
            }
            if payment_method_id:
                subscription_params["default_payment_method"] = payment_method_id

            subscription = stripe.Subscription.create(**subscription_params)
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create subscription: {e}")
            raise

    async def create_invoice_item(
        self,
        customer_id: str,
        amount: int,
        currency: str,
        description: str,
        invoice_date: Optional[datetime] = None,
        metadata: Dict = None
    ) -> Dict:
        """Create invoice item for usage-based billing"""
        try:
            params = {
                "customer": customer_id,
                "amount": amount,
                "currency": currency,
                "description": description,
                "metadata": metadata or {}
            }
            if invoice_date:
                params["invoice_datetime"] = int(invoice_date.timestamp())
                
            invoice_item = stripe.InvoiceItem.create(**params)
            return invoice_item
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create invoice item: {e}")
            raise

    async def handle_webhook(self, payload: bytes, sig_header: str, endpoint_secret: str) -> Dict:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
            handler = self.webhook_handlers.get(event["type"])
            if handler:
                return await handler(event["data"]["object"])
            return {"status": "unhandled_event_type"}
        except stripe.error.StripeError as e:
            logger.error(f"Webhook error: {e}")
            raise

    async def _handle_successful_payment(self, invoice: Dict) -> Dict:
        """Handle successful payment webhook"""
        amount = invoice["amount_paid"]
        customer_id = invoice["customer"]
        
        # Record payment in revenue events
        # TODO: Integrate with revenue_events table
        logger.info(f"Recording successful payment of {amount} for customer {customer_id}")
        return {"status": "processed"}

    async def _handle_failed_payment(self, invoice: Dict) -> Dict:
        """Handle failed payment webhook"""
        customer_id = invoice["customer"]
        attempts = invoice["attempt_count"]
        
        if attempts >= 3:
            logger.error(f"Final payment failure for customer {customer_id}")
            # TODO: Cancel subscription after max attempts
        else:
            logger.warning(f"Payment failed (attempt {attempts}) for customer {customer_id}")
        
        return {"status": "processed"}

    async def _handle_subscription_ended(self, subscription: Dict) -> Dict:
        """Handle subscription cancellation"""
        customer_id = subscription["customer"]
        logger.info(f"Subscription ended for customer {customer_id}")
        # TODO: Churn analysis and retention logic
        return {"status": "processed"}
