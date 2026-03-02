import os
import stripe
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    async def create_customer(self, email: str, name: str = None) -> Dict[str, Any]:
        """Create a new Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={
                    'signup_date': datetime.utcnow().isoformat()
                }
            )
            logger.info(f"Created customer {customer.id}")
            return {
                'success': True,
                'customer_id': customer.id,
                'customer_email': customer.email
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create a subscription for the customer."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent'],
                metadata=metadata or {}
            )
            
            logger.info(f"Created subscription {subscription.id} for customer {customer_id}")
            return {
                'success': True,
                'subscription_id': subscription.id,
                'client_secret': subscription.latest_invoice.payment_intent.client_secret,
                'status': subscription.status
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    async def handle_webhook(self, payload: str, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            logger.info(f"Processing webhook event: {event.type}")

            event_type = event['type']
            data = event['data']
            
            if event_type == 'payment_intent.succeeded':
                return await self._handle_payment_succeeded(data.object)
            elif event_type == 'payment_intent.payment_failed':
                return await self._handle_payment_failed(data.object)
            elif event_type == 'invoice.paid':
                return await self._handle_invoice_paid(data.object)
            elif event_type == 'invoice.payment_failed':
                return await self._handle_payment_failed(data.object)
            else:
                return {'success': True, 'processed': False, 'event_type': event_type}

        except ValueError as e:
            logger.error(f"Invalid payload: {str(e)}")
            raise
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Webhook handler error: {str(e)}")
            raise

    async def _handle_payment_succeeded(self, payment_intent):
        """Handle successful payment."""
        # Implementation for provisioning service
        logger.info(f"Payment succeeded: {payment_intent.id}")
        return {'success': True, 'processed': True}

    async def _handle_payment_failed(self, payment_intent):
        """Handle failed payment."""
        logger.warning(f"Payment failed: {payment_intent.id}")
        # Implement retry or notify logic
        return {'success': True, 'processed': True}

    async def _handle_invoice_paid(self, invoice):
        """Handle completed invoice payment."""
        logger.info(f"Invoice paid: {invoice.id}")
        # Implement provisioning logic
        return {'success': True, 'processed': True}
