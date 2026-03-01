import os
import stripe
import json
from typing import Dict, Optional
from datetime import datetime

class PaymentService:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    async def create_checkout_session(
        self, 
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create Stripe checkout session"""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata or {}
            )
            return {
                'success': True,
                'session_id': session.id,
                'url': session.url
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict:
        """Handle Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                await self._fulfill_order(session)
                
            return {'success': True}
        except ValueError as e:
            return {'success': False, 'error': 'Invalid payload'}
        except stripe.error.SignatureVerificationError as e:
            return {'success': False, 'error': 'Invalid signature'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _fulfill_order(self, session: Dict) -> None:
        """Fulfill order after successful payment"""
        # TODO: Implement order fulfillment logic
        # This would trigger your product delivery/service activation
        print(f"Fulfilling order for {session['id']}")
