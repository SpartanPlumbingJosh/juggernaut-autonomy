"""
Payment processing service with Stripe integration.
Handles payment methods, charges, subscriptions and webhooks.
"""
import logging
import stripe
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.config import settings

logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

class PaymentService:
    def __init__(self):
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    async def create_customer(self, user_id: str, email: str, name: str) -> Dict[str, Any]:
        """Create a Stripe customer tied to our user"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={
                    'user_id': user_id,
                    'created_at': datetime.utcnow().isoformat()
                }
            )
            return {
                'success': True,
                'customer_id': customer.id,
                'payment_methods': []
            }
        except stripe.error.StripeError as e:
            logger.error(f"Error creating customer: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def attach_payment_method(self, customer_id: str, payment_method_id: str) -> Dict[str, Any]:
        """Attach payment method to customer"""
        try:
            payment_method = stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            return {
                'success': True,
                'payment_method': payment_method.id
            }
        except stripe.error.StripeError as e:
            logger.error(f"Error attaching payment method: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        payment_method_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new subscription"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent'],
                off_session=True
            )
            return {
                'success': True,
                'subscription_id': subscription.id,
                'payment_intent': subscription.latest_invoice.payment_intent
            }
        except stripe.error.StripeError as e:
            logger.error(f"Error creating subscription: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event.type == 'invoice.payment_succeeded':
                return await self._handle_payment_success(event.data.object)
            elif event.type == 'invoice.payment_failed':
                return await self._handle_payment_failure(event.data.object)
            elif event.type == 'customer.subscription.deleted':
                return await self._handle_subscription_canceled(event.data.object)
            
            return {'success': True, 'handled': False}
        except stripe.error.StripeError as e:
            logger.error(f"Webhook error: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def _handle_payment_success(self, invoice) -> Dict[str, Any]:
        """Record successful payment in our system"""
        # Implementation would record the payment in revenue_events
        # and update subscription status
        return {'success': True, 'handled': True}

    async def _handle_payment_failure(self, invoice) -> Dict[str, Any]:
        """Attempt to recover failed payments"""
        # Implementation would:
        # 1. Notify customer
        # 2. Retry payment if possible 
        # 3. Update subscription status if needed
        return {'success': True, 'handled': True}

    async def _handle_subscription_canceled(self, subscription) -> Dict[str, Any]:
        """Handle subscription cancellation"""
        # Flag as canceled in our database
        return {'success': True, 'handled': True}
