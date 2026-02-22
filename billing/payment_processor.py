"""
Payment processing system with Stripe and PayPal integrations.
Handles subscriptions, one-time payments, and webhook events.
"""

import os
import json
import stripe
import logging
from datetime import datetime
from typing import Dict, Optional, List

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe.api_version = '2023-08-16'

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self):
        self.providers = {
            'stripe': self._process_stripe_payment,
            'paypal': self._process_paypal_payment
        }

    async def create_customer(self, user_id: str, email: str, name: str) -> Dict:
        """Create a customer in Stripe."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={'user_id': user_id}
            )
            return {'success': True, 'customer_id': customer.id}
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        payment_method_id: str = None
    ) -> Dict:
        """Create a subscription for a customer."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent'],
                metadata={'created_at': datetime.utcnow().isoformat()}
            )
            
            return {
                'success': True,
                'subscription_id': subscription.id,
                'client_secret': subscription.latest_invoice.payment_intent.client_secret
            }
        except stripe.error.StripeError as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def process_payment(
        self,
        amount: int,
        currency: str,
        payment_method: str,
        payment_method_id: str,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Process a payment through Stripe or PayPal."""
        processor = self.providers.get(payment_method.lower())
        if not processor:
            return {'success': False, 'error': 'Unsupported payment method'}
        
        return await processor(
            amount=amount,
            currency=currency,
            payment_method_id=payment_method_id,
            customer_id=customer_id,
            metadata=metadata
        )

    async def _process_stripe_payment(
        self,
        amount: int,
        currency: str,
        payment_method_id: str,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Process payment through Stripe."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                payment_method=payment_method_id,
                customer=customer_id,
                confirm=True,
                metadata=metadata or {},
                off_session=True
            )
            return {'success': True, 'payment_id': intent.id}
        except stripe.error.StripeError as e:
            logger.error(f"Stripe payment failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_webhook(self, payload: str, sig_header: str, endpoint_secret: str) -> Dict:
        """Handle Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {str(e)}")
            return {'success': False, 'error': 'Invalid payload'}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            return {'success': False, 'error': 'Invalid signature'}

        # Process the event
        event_type = event['type']
        data = event['data']['object']
        
        if event_type == 'payment_intent.succeeded':
            await self._handle_payment_success(data)
        elif event_type == 'invoice.payment_succeeded':
            await self._handle_subscription_payment(data)
        elif event_type == 'customer.subscription.deleted':
            await self._handle_subscription_canceled(data)
        
        return {'success': True, 'event': event_type}

    async def _handle_payment_success(self, payment_intent: Dict) -> None:
        """Handle successful one-time payment."""
        # Record revenue event
        amount = payment_intent['amount_received']
        metadata = payment_intent.get('metadata', {})
        await self._record_revenue_event(
            amount=amount,
            event_type='revenue',
            source='stripe',
            metadata=metadata
        )

    async def _handle_subscription_payment(self, invoice: Dict) -> None:
        """Handle successful subscription payment."""
        amount = invoice['amount_paid']
        subscription_id = invoice['subscription']
        metadata = {
            'subscription_id': subscription_id,
            'invoice_id': invoice['id']
        }
        await self._record_revenue_event(
            amount=amount,
            event_type='revenue',
            source='stripe_subscription',
            metadata=metadata
        )

    async def _handle_subscription_canceled(self, subscription: Dict) -> None:
        """Handle subscription cancellation."""
        # Update subscription status in database
        pass

    async def _record_revenue_event(
        self,
        amount: int,
        event_type: str,
        source: str,
        metadata: Dict
    ) -> None:
        """Record revenue event in database."""
        # Implement database recording logic
        pass
