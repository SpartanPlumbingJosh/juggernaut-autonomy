import os
import stripe
import logging
from typing import Dict, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Handle payment processing with Stripe integration."""
    
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
    async def create_payment_intent(
        self, 
        amount: int, 
        currency: str = 'usd',
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create a payment intent with Stripe."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            logger.info(f"Created payment intent {intent.id}")
            return {
                'success': True,
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id
            }
        except Exception as e:
            logger.error(f"Payment intent creation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    async def handle_webhook(self, payload: str, sig_header: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                await self._handle_successful_payment(payment_intent)
                
            elif event['type'] == 'payment_intent.payment_failed':
                payment_intent = event['data']['object']
                await self._handle_failed_payment(payment_intent)
                
            return {'success': True}
            
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {str(e)}")
            return {'success': False, 'error': 'Invalid payload'}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {str(e)}")
            return {'success': False, 'error': 'Invalid signature'}
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    async def _handle_successful_payment(self, payment_intent: Dict) -> None:
        """Process successful payment."""
        amount = payment_intent['amount'] / 100  # Convert to dollars
        metadata = payment_intent.get('metadata', {})
        
        logger.info(
            f"Payment succeeded: {payment_intent['id']} "
            f"Amount: {amount} {payment_intent['currency']}"
        )
        
        # TODO: Trigger fulfillment pipeline
        # await self.fulfillment_service.process(metadata)

    async def _handle_failed_payment(self, payment_intent: Dict) -> None:
        """Process failed payment."""
        last_error = payment_intent.get('last_payment_error', {})
        logger.error(
            f"Payment failed: {payment_intent['id']} "
            f"Reason: {last_error.get('message', 'unknown')}"
        )
