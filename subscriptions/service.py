import stripe
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from .models import Subscription, SubscriptionStatus, SubscriptionPlan, PaymentMethod

class SubscriptionService:
    def __init__(self, stripe_api_key: str):
        stripe.api_key = stripe_api_key
        self.logger = logging.getLogger(__name__)

    def create_customer(self, email: str, name: str, payment_method_id: str) -> Dict[str, Any]:
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                payment_method=payment_method_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )
            return customer
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to create customer: {str(e)}")
            raise

    def create_subscription(self, customer_id: str, plan_id: str, trial_period_days: int = 0) -> Subscription:
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': plan_id}],
                trial_period_days=trial_period_days,
                expand=['latest_invoice.payment_intent']
            )
            return self._map_stripe_subscription(subscription)
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to create subscription: {str(e)}")
            raise

    def cancel_subscription(self, subscription_id: str) -> Subscription:
        try:
            subscription = stripe.Subscription.delete(subscription_id)
            return self._map_stripe_subscription(subscription)
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to cancel subscription: {str(e)}")
            raise

    def update_payment_method(self, customer_id: str, payment_method_id: str) -> PaymentMethod:
        try:
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id,
            )
            
            # Set as default payment method
            stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )
            
            payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
            return self._map_stripe_payment_method(payment_method)
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to update payment method: {str(e)}")
            raise

    def handle_webhook_event(self, payload: str, sig_header: str, webhook_secret: str) -> bool:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'invoice.payment_succeeded':
                self._handle_payment_success(event['data']['object'])
            elif event['type'] == 'invoice.payment_failed':
                self._handle_payment_failure(event['data']['object'])
            elif event['type'] == 'customer.subscription.updated':
                self._handle_subscription_update(event['data']['object'])
            
            return True
        except stripe.error.SignatureVerificationError as e:
            self.logger.error(f"Webhook signature verification failed: {str(e)}")
            return False
        except stripe.error.StripeError as e:
            self.logger.error(f"Webhook processing failed: {str(e)}")
            return False

    def _map_stripe_subscription(self, stripe_subscription) -> Subscription:
        return Subscription(
            id=stripe_subscription.id,
            customer_id=stripe_subscription.customer,
            plan_id=stripe_subscription.items.data[0].price.id,
            status=SubscriptionStatus(stripe_subscription.status),
            current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
            current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
            cancel_at_period_end=stripe_subscription.cancel_at_period_end,
            trial_end=datetime.fromtimestamp(stripe_subscription.trial_end) if stripe_subscription.trial_end else None
        )

    def _map_stripe_payment_method(self, stripe_payment_method) -> PaymentMethod:
        return PaymentMethod(
            id=stripe_payment_method.id,
            customer_id=stripe_payment_method.customer,
            type=stripe_payment_method.type,
            last4=stripe_payment_method.card.last4,
            exp_month=stripe_payment_method.card.exp_month,
            exp_year=stripe_payment_method.card.exp_year,
            brand=stripe_payment_method.card.brand
        )

    def _handle_payment_success(self, invoice):
        # Handle successful payment
        pass

    def _handle_payment_failure(self, invoice):
        # Handle payment failure
        pass

    def _handle_subscription_update(self, subscription):
        # Handle subscription changes
        pass
