import os
import stripe
import logging
from typing import Optional, Dict, Any
from datetime import datetime

class PaymentService:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
    async def create_checkout_session(self, price_id: str, customer_email: str) -> Dict[str, Any]:
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='payment',
                customer_email=customer_email,
                success_url=os.getenv('PAYMENT_SUCCESS_URL'),
                cancel_url=os.getenv('PAYMENT_CANCEL_URL'),
            )
            return {'success': True, 'session_id': session.id, 'url': session.url}
        except Exception as e:
            logging.error(f"Payment session creation failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_webhook(self, payload: str, sig_header: str) -> Optional[Dict[str, Any]]:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                return await self._process_payment_success(session)
            
            return None
        except Exception as e:
            logging.error(f"Webhook processing failed: {str(e)}")
            return None

    async def _process_payment_success(self, session: Dict[str, Any]) -> Dict[str, Any]:
        amount = session.get('amount_total', 0)
        customer_email = session.get('customer_email', '')
        
        revenue_event = {
            'event_type': 'revenue',
            'amount_cents': amount,
            'currency': session.get('currency', 'usd'),
            'source': 'stripe',
            'customer_email': customer_email,
            'payment_id': session.get('id'),
            'recorded_at': datetime.utcnow().isoformat(),
            'metadata': {
                'payment_method': session.get('payment_method_types', ['card'])[0],
                'session_details': session
            }
        }
        
        return {'success': True, 'data': revenue_event}
