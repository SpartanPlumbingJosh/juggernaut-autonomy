import os
import stripe
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    def create_checkout_session(self, price_id: str, customer_email: str, metadata: Dict) -> Dict:
        """Create Stripe checkout session"""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='payment',
                customer_email=customer_email,
                metadata=metadata,
                success_url=os.getenv('PAYMENT_SUCCESS_URL'),
                cancel_url=os.getenv('PAYMENT_CANCEL_URL'),
            )
            return {'success': True, 'session_id': session.id, 'url': session.url}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def handle_webhook(self, payload: str, sig_header: str) -> Dict:
        """Process Stripe webhook event"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                self._process_payment_success(
                    session['id'],
                    session['customer_email'],
                    session['amount_total'],
                    session['metadata']
                )
            
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _process_payment_success(self, session_id: str, email: str, amount: int, metadata: Dict) -> None:
        """Record successful payment and trigger fulfillment"""
        # Record in revenue_events
        # Trigger onboarding workflow
        pass
