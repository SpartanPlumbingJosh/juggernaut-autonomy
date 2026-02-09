import stripe
import logging
from datetime import datetime
from typing import Optional, Dict, Any

class PaymentProcessor:
    def __init__(self, secret_key: str, webhook_secret: str):
        """Initialize Stripe payment processor."""
        stripe.api_key = secret_key
        self.webhook_secret = webhook_secret
        self.logger = logging.getLogger(__name__)

    async def create_payment_intent(
        self,
        amount: int,
        currency: str,
        metadata: Optional[Dict[str, Any]] = None,
        customer_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a payment intent with Stripe."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                automatic_payment_methods={
                    'enabled': True,
                },
                metadata=metadata or {},
                receipt_email=customer_email
            )
            return {
                'success': True,
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id
            }
        except stripe.error.StripeError as e:
            self.logger.error(f"Payment intent creation failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
        except ValueError as e:
            self.logger.error(f"Invalid payload: {str(e)}")
            return {'success': False, 'error': 'Invalid payload'}
        except stripe.error.SignatureVerificationError as e:
            self.logger.error(f"Invalid signature: {str(e)}")
            return {'success': False, 'error': 'Invalid signature'}

        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            self.logger.info(f"Payment succeeded: {payment_intent['id']}")
            # TODO: Trigger fulfillment process
            return {
                'success': True,
                'event': 'payment_intent.succeeded',
                'payment_intent_id': payment_intent['id'],
                'amount': payment_intent['amount'],
                'metadata': payment_intent.get('metadata', {})
            }
        elif event['type'] == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            self.logger.warning(f"Payment failed: {payment_intent['id']}")
            return {
                'success': True,
                'event': 'payment_intent.payment_failed',
                'payment_intent_id': payment_intent['id'],
                'error': payment_intent.get('last_payment_error', {}).get('message', '')
            }
        else:
            self.logger.info(f"Unhandled event type: {event['type']}")
            return {'success': True, 'event': event['type'], 'handled': False}

    async def refund_payment(self, payment_intent_id: str, amount: Optional[int] = None) -> Dict[str, Any]:
        """Process a refund through Stripe."""
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_intent_id,
                amount=amount  # None means full refund
            )
            return {'success': True, 'refund_id': refund.id, 'status': refund.status}
        except stripe.error.StripeError as e:
            self.logger.error(f"Refund failed: {str(e)}")
            return {'success': False, 'error': str(e)}
