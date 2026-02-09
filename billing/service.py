import stripe
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from .models import Subscription, SubscriptionPlan, Invoice, SubscriptionStatus

class BillingService:
    def __init__(self, stripe_api_key: str):
        stripe.api_key = stripe_api_key
        self.logger = logging.getLogger(__name__)

    def create_customer(self, email: str, name: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return customer.id
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to create customer: {str(e)}")
            return None

    def create_subscription(self, 
                          customer_id: str,
                          plan_id: str,
                          trial_period_days: Optional[int] = None) -> Optional[Subscription]:
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id}],
                trial_period_days=trial_period_days
            )
            return Subscription(
                id=subscription.id,
                customer_id=customer_id,
                plan_id=plan_id,
                status=SubscriptionStatus(subscription.status),
                current_period_start=datetime.fromtimestamp(subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(subscription.current_period_end),
                cancel_at_period_end=subscription.cancel_at_period_end,
                metadata=subscription.metadata
            )
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to create subscription: {str(e)}")
            return None

    def cancel_subscription(self, subscription_id: str) -> bool:
        try:
            stripe.Subscription.delete(subscription_id)
            return True
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to cancel subscription: {str(e)}")
            return False

    def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return Subscription(
                id=subscription.id,
                customer_id=subscription.customer,
                plan_id=subscription.items.data[0].price.id,
                status=SubscriptionStatus(subscription.status),
                current_period_start=datetime.fromtimestamp(subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(subscription.current_period_end),
                cancel_at_period_end=subscription.cancel_at_period_end,
                metadata=subscription.metadata
            )
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to get subscription: {str(e)}")
            return None

    def create_invoice(self, customer_id: str, amount_cents: int, currency: str) -> Optional[Invoice]:
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                auto_advance=True,
                collection_method='charge_automatically',
                currency=currency,
                description="Usage-based invoice",
                metadata={"type": "usage_based"}
            )
            return Invoice(
                id=invoice.id,
                customer_id=customer_id,
                amount_due_cents=amount_cents,
                currency=currency,
                status=invoice.status,
                created=datetime.fromtimestamp(invoice.created),
                period_start=datetime.fromtimestamp(invoice.period_start),
                period_end=datetime.fromtimestamp(invoice.period_end),
                paid=invoice.paid
            )
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to create invoice: {str(e)}")
            return None

    def process_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> bool:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event.type == 'invoice.payment_succeeded':
                self._handle_payment_success(event.data.object)
            elif event.type == 'invoice.payment_failed':
                self._handle_payment_failure(event.data.object)
            elif event.type == 'customer.subscription.deleted':
                self._handle_subscription_cancelled(event.data.object)
            
            return True
        except stripe.error.SignatureVerificationError as e:
            self.logger.error(f"Webhook signature verification failed: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Webhook processing failed: {str(e)}")
            return False

    def _handle_payment_success(self, invoice: Dict[str, Any]) -> None:
        # Update your system with successful payment
        pass

    def _handle_payment_failure(self, invoice: Dict[str, Any]) -> None:
        # Handle payment failure (e.g., notify customer, retry logic)
        pass

    def _handle_subscription_cancelled(self, subscription: Dict[str, Any]) -> None:
        # Handle subscription cancellation
        pass
