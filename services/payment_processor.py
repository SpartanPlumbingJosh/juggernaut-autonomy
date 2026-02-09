import stripe
import json
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self, stripe_secret_key: str):
        stripe.api_key = stripe_secret_key
        
    def create_payment_intent(self, amount_cents: int, currency: str, metadata: Dict) -> Dict:
        """Create a Stripe payment intent"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata,
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            return {
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'status': intent.status
            }
        except Exception as e:
            return {'error': str(e)}
            
    def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                return self._process_successful_payment(payment_intent)
                
            return {'status': 'unhandled_event'}
        except Exception as e:
            return {'error': str(e)}
            
    def _process_successful_payment(self, payment_intent: Dict) -> Dict:
        """Handle successful payment"""
        metadata = payment_intent.get('metadata', {})
        return {
            'status': 'success',
            'payment_intent_id': payment_intent['id'],
            'amount': payment_intent['amount'],
            'currency': payment_intent['currency'],
            'metadata': metadata,
            'timestamp': datetime.utcnow().isoformat()
        }
