import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import stripe
from fastapi import HTTPException

from billing.models import (
    SubscriptionStatus,
    SubscriptionPlan,
    Subscription,
    Invoice,
    PaymentMethod,
    Customer
)

logger = logging.getLogger(__name__)

class BillingService:
    def __init__(self, stripe_api_key: str):
        stripe.api_key = stripe_api_key

    async def create_customer(self, email: str, name: Optional[str] = None) -> Customer:
        """Create a new customer in Stripe"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={}
            )
            return Customer(**customer)
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create customer: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method_id: str) -> Subscription:
        """Create a new subscription"""
        try:
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            # Set as default payment method
            stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )
            
            # Create subscription
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': plan_id}],
                expand=['latest_invoice.payment_intent']
            )
            return Subscription(**subscription)
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def cancel_subscription(self, subscription_id: str) -> Subscription:
        """Cancel a subscription"""
        try:
            subscription = stripe.Subscription.delete(subscription_id)
            return Subscription(**subscription)
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def update_subscription_plan(self, subscription_id: str, new_plan_id: str) -> Subscription:
        """Update subscription to a new plan"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            updated_subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=False,
                items=[{
                    'id': subscription['items']['data'][0].id,
                    'price': new_plan_id,
                }]
            )
            return Subscription(**updated_subscription)
        except stripe.error.StripeError as e:
            logger.error(f"Failed to update subscription plan: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def handle_webhook_event(self, payload: bytes, sig_header: str, webhook_secret: str) -> None:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'invoice.payment_succeeded':
                await self._handle_successful_payment(event)
            elif event['type'] == 'invoice.payment_failed':
                await self._handle_failed_payment(event)
            elif event['type'] == 'customer.subscription.updated':
                await self._handle_subscription_update(event)
            elif event['type'] == 'customer.subscription.deleted':
                await self._handle_subscription_cancellation(event)
                
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _handle_successful_payment(self, event: Dict) -> None:
        """Handle successful payment webhook"""
        invoice = event['data']['object']
        # Record revenue event
        # Update subscription status
        # Send receipt email
        pass

    async def _handle_failed_payment(self, event: Dict) -> None:
        """Handle failed payment webhook"""
        invoice = event['data']['object']
        # Update subscription status
        # Send dunning email
        # Retry payment logic
        pass

    async def _handle_subscription_update(self, event: Dict) -> None:
        """Handle subscription update webhook"""
        subscription = event['data']['object']
        # Update subscription in database
        # Handle plan changes
        pass

    async def _handle_subscription_cancellation(self, event: Dict) -> None:
        """Handle subscription cancellation webhook"""
        subscription = event['data']['object']
        # Update subscription status
        # Send cancellation confirmation
        pass
