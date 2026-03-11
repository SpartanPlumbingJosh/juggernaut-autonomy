import stripe
import logging
from datetime import datetime
from typing import Dict, Optional

class PaymentProcessor:
    def __init__(self, stripe_api_key: str):
        self.stripe = stripe
        self.stripe.api_key = stripe_api_key
        self.logger = logging.getLogger(__name__)

    async def create_payment_intent(self, amount: int, currency: str, metadata: Dict) -> Optional[Dict]:
        """Create a Stripe payment intent"""
        try:
            intent = self.stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata,
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            self.logger.info(f"Created payment intent: {intent.id}")
            return intent
        except self.stripe.error.StripeError as e:
            self.logger.error(f"Payment intent creation failed: {str(e)}")
            return None

    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> bool:
        """Process Stripe webhook events"""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                await self._handle_successful_payment(payment_intent)
                return True
                
            elif event['type'] == 'payment_intent.payment_failed':
                payment_intent = event['data']['object']
                await self._handle_failed_payment(payment_intent)
                return True
                
        except self.stripe.error.StripeError as e:
            self.logger.error(f"Webhook processing failed: {str(e)}")
            return False

    async def _handle_successful_payment(self, payment_intent: Dict) -> None:
        """Handle successful payment"""
        try:
            # Record revenue event
            metadata = payment_intent.get('metadata', {})
            await self._record_revenue_event(
                amount=payment_intent['amount'],
                currency=payment_intent['currency'],
                metadata=metadata
            )
            self.logger.info(f"Payment succeeded: {payment_intent['id']}")
            
        except Exception as e:
            self.logger.error(f"Failed to handle successful payment: {str(e)}")

    async def _handle_failed_payment(self, payment_intent: Dict) -> None:
        """Handle failed payment"""
        self.logger.warning(f"Payment failed: {payment_intent['id']}")
        # Implement retry logic or notify customer

    async def _record_revenue_event(self, amount: int, currency: str, metadata: Dict) -> None:
        """Record revenue event in database"""
        # Implementation depends on your database setup
        pass
