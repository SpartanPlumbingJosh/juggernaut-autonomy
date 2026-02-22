"""
Stripe integration for payment processing and subscription management.
"""
import stripe
import logging
from typing import Dict, Optional

class StripePaymentProcessor:
    def __init__(self, api_key: str, webhook_secret: str):
        self.client = stripe
        self.client.api_key = api_key
        self.webhook_secret = webhook_secret
        
    def create_customer(self, email: str, name: str, metadata: Optional[Dict]=None) -> Dict:
        """Register a new customer in Stripe."""
        try:
            customer = self.client.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {'success': True, 'customer_id': customer.id}
        except Exception as e:
            logging.error(f"Stripe customer creation failed: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a new subscription for a customer."""
        try:
            subscription = self.client.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            return {
                'success': True,
                'subscription_id': subscription.id,
                'client_secret': subscription.latest_invoice.payment_intent.client_secret
            }
        except Exception as e:
            logging.error(f"Stripe subscription creation failed: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def handle_webhook(self, payload: str, sig_header: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = self.client.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            event_map = {
                'invoice.paid': self._handle_payment_succeeded,
                'invoice.payment_failed': self._handle_payment_failed,
                'customer.subscription.deleted': self._handle_subscription_ended
            }
            
            handler = event_map.get(event['type'])
            if handler:
                return handler(event)
            return {'success': False, 'error': 'Unhandled event type'}
        except Exception as e:
            logging.error(f"Stripe webhook processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}
