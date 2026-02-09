import stripe
from datetime import datetime
from typing import Dict, Optional
import logging

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.logger = logging.getLogger(__name__)

    def create_customer(self, email: str, name: str) -> Dict:
        """Create a new customer in payment system."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={'onboarded_at': datetime.utcnow().isoformat()}
            )
            return {
                'success': True,
                'customer_id': customer.id,
                'email': customer.email
            }
        except Exception as e:
            self.logger.error(f"Failed to create customer: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create recurring subscription."""
        try:
            subscription = stripe.Subscription.create(
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
            self.logger.error(f"Failed to create subscription: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict:
        """Process payment webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                return self._handle_payment_success(event)
            elif event['type'] == 'invoice.payment_failed':
                return self._handle_payment_failure(event)
            
            return {'success': True, 'handled': False}
        except Exception as e:
            self.logger.error(f"Webhook error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _handle_payment_success(self, event: Dict) -> Dict:
        """Handle successful payment."""
        # TODO: Trigger service delivery
        return {'success': True, 'handled': True}

    def _handle_payment_failure(self, event: Dict) -> Dict:
        """Handle failed payment."""
        # TODO: Trigger retry or notification
        return {'success': True, 'handled': True}
