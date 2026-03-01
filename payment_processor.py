import stripe
from typing import Dict, Any
from datetime import datetime
import json
import os

stripe.api_key = os.getenv('STRIPE_API_KEY')

class PaymentProcessor:
    """Handles Stripe payment processing and webhook events"""
    
    @classmethod
    def create_checkout_session(cls, product_id: str, customer_email: str) -> Dict[str, Any]:
        """Create Stripe checkout session"""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': product_id,
                    'quantity': 1,
                }],
                mode='payment',
                customer_email=customer_email,
                success_url=os.getenv('PAYMENT_SUCCESS_URL') + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=os.getenv('PAYMENT_CANCEL_URL'),
            )
            return {'success': True, 'session_id': session.id, 'session_url': session.url}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def handle_webhook(cls, payload: str, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook event"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
            )
            
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                amount = session['amount_total']  # in cents
                
                # Record revenue event
                return {
                    'success': True,
                    'event': 'payment_succeeded',
                    'data': {
                        'payment_id': session.id,
                        'email': session.get('customer_email'),
                        'amount_cents': amount,
                        'timestamp': datetime.fromtimestamp(session.created),
                        'metadata': session.metadata
                    }
                }
            
            return {'success': True, 'event': event['type']}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
