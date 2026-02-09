import os
import stripe
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    """Handle payment processing through Stripe and other gateways."""
    
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.currency = 'usd'
        
    async def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new customer in Stripe."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {
                'success': True,
                'customer_id': customer.id,
                'details': customer
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
            
    async def create_payment_intent(self, amount: int, customer_id: str, description: str) -> Dict:
        """Create a payment intent for a customer."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=self.currency,
                customer=customer_id,
                description=description,
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            return {
                'success': True,
                'client_secret': intent.client_secret,
                'payment_id': intent.id
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
            
    async def handle_webhook(self, payload: str, sig_header: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
            )
            
            # Handle different event types
            if event['type'] == 'payment_intent.succeeded':
                return self._handle_payment_success(event)
            elif event['type'] == 'payment_intent.payment_failed':
                return self._handle_payment_failure(event)
            else:
                return {'success': True, 'handled': False}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    def _handle_payment_success(self, event: Dict) -> Dict:
        """Handle successful payment event."""
        payment_intent = event['data']['object']
        return {
            'success': True,
            'handled': True,
            'action': 'payment_success',
            'payment_id': payment_intent['id'],
            'amount': payment_intent['amount'],
            'timestamp': datetime.utcnow().isoformat()
        }
        
    def _handle_payment_failure(self, event: Dict) -> Dict:
        """Handle failed payment event."""
        payment_intent = event['data']['object']
        return {
            'success': True,
            'handled': True,
            'action': 'payment_failure',
            'payment_id': payment_intent['id'],
            'error': payment_intent['last_payment_error'],
            'timestamp': datetime.utcnow().isoformat()
        }
