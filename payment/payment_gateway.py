import stripe
import logging
from typing import Dict, Optional
from datetime import datetime

class PaymentGateway:
    def __init__(self, stripe_secret_key: str):
        stripe.api_key = stripe_secret_key
        self.logger = logging.getLogger(__name__)

    def create_payment_intent(self, amount: int, currency: str = 'usd', metadata: Optional[Dict] = None) -> Dict:
        """Create a Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={'enabled': True},
            )
            return {'success': True, 'client_secret': intent.client_secret}
        except Exception as e:
            self.logger.error(f"Payment intent creation failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict:
        """Handle Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                self._process_successful_payment(payment_intent)
                
            return {'success': True}
        except Exception as e:
            self.logger.error(f"Webhook processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _process_successful_payment(self, payment_intent: Dict) -> None:
        """Process a successful payment."""
        metadata = payment_intent.get('metadata', {})
        self.logger.info(f"Payment succeeded: {payment_intent['id']}")
        # Trigger delivery and onboarding flow here
