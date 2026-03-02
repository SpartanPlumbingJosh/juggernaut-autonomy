import stripe
import os
from typing import Dict, Any
from datetime import datetime

class StripePaymentProcessor:
    def __init__(self):
        self.stripe_api_key = os.getenv('STRIPE_API_KEY')
        stripe.api_key = self.stripe_api_key
        
    def create_payment_link(
        self,
        price: float,
        product_name: str,
        metadata: Dict[str, Any],
        success_url: str,
        cancel_url: str
    ) -> Dict[str, Any]:
        try:
            product = stripe.Product.create(name=product_name)
            price = stripe.Price.create(
                product=product.id,
                unit_amount=int(price*100),
                currency='usd'
            )
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price.id,
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata
            )
            return {
                'success': True,
                'url': session.url,
                'session_id': session.id
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def handle_webhook_event(self, payload: str, sig_header: str) -> Dict[str, Any]:
        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                os.getenv('STRIPE_WEBHOOK_SECRET')
            )
            
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                metadata = session.get('metadata', {})
                
                return {
                    'success': True,
                    'event': 'payment_success',
                    'session_id': session['id'],
                    'amount': session['amount_total'] / 100,
                    'metadata': metadata
                }
            
            return {'success': False, 'error': 'Unhandled event type'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
