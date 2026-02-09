import os
import stripe
import logging
from datetime import datetime
from typing import Any, Dict, Optional, List

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
logger = logging.getLogger(__name__)

class StripeIntegration:
    """Handles all Stripe payment operations."""

    @staticmethod
    def create_customer(email: str, name: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a Stripe customer.
        
        Args:
            email: Customer email
            name: Customer name
            metadata: Additional customer metadata
            
        Returns:
            Stripe customer object
        """
        try:
            return stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
        except Exception as e:
            logger.error(f"Failed to create Stripe customer: {str(e)}")
            raise

    @staticmethod
    def create_subscription(
        customer_id: str,
        price_id: str,
        payment_behavior: str = 'default_incomplete',
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a subscription for a customer.
        
        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID for subscription
            payment_behavior: Payment behavior ('default_incomplete')
            metadata: Additional subscription metadata
            
        Returns:
            Stripe subscription object
        """
        try:
            return stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                payment_behavior=payment_behavior,
                metadata=metadata or {},
                expand=['latest_invoice.payment_intent']
            )
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            raise

    @staticmethod
    def record_usage(subscription_item_id: str, quantity: int, timestamp: Optional[int] = None) -> None:
        """
        Record usage for metered billing.
        
        Args:
            subscription_item_id: The subscription item ID
            quantity: Quantity to record
            timestamp: Unix timestamp for usage (defaults to now)
        """
        try:
            stripe.SubscriptionItem.create_usage_record(
                subscription_item_id,
                quantity=quantity,
                timestamp=timestamp or int(datetime.now().timestamp())
            )
        except Exception as e:
            logger.error(f"Failed to record usage: {str(e)}")
            raise

    @staticmethod
    def handle_webhook(payload: str, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """
        Process Stripe webhook events.
        
        Args:
            payload: Request payload string
            sig_header: Stripe-Signature header
            webhook_secret: Webhook signing secret
            
        Returns:
            Processed event response
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            # Subscription lifecycle events
            if event['type'] == 'invoice.paid':
                invoice = event['data']['object']
                # Record successful payment
                return {
                    'status': 'success',
                    'action': 'payment_recorded',
                    'amount_received': invoice['amount_paid'],
                    'customer_id': invoice['customer']
                }
                
            elif event['type'] == 'invoice.payment_failed':
                invoice = event['data']['object']
                # Handle payment failure
                return {
                    'status': 'pending',
                    'action': 'payment_failed',
                    'amount_due': invoice['amount_due'],
                    'customer_id': invoice['customer']
                }
                
            elif event['type'] == 'customer.subscription.deleted':
                subscription = event['data']['object']
                # Handle canceled subscription
                return {
                    'status': 'canceled',
                    'action': 'subscription_canceled',
                    'customer_id': subscription['customer']
                }
                
            return {'status': 'processed', 'event': event['type']}
            
        except ValueError as e:
            logger.error(f"Invalid Stripe webhook payload: {str(e)}")
            raise
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid Stripe signature: {str(e)}")
            raise
            
    @staticmethod
    def retry_failed_payment(payment_intent_id: str) -> Dict[str, Any]:
        """
        Retry a failed payment.
        
        Args:
            payment_intent_id: ID of payment intent to retry
            
        Returns:
            Result of payment retry
        """
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            if payment_intent.status == 'requires_payment_method':
                return stripe.PaymentIntent.confirm(payment_intent.id)
            return {"status": payment_intent.status}
        except Exception as e:
            logger.error(f"Failed to retry payment: {str(e)}")
            raise
