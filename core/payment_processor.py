"""
Payment Processor - Handles payment integrations and processing.
Currently supports Stripe as payment gateway.
"""

import os
import logging
from typing import Dict, Optional

import stripe

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe.api_version = '2023-08-16'
logger = logging.getLogger(__name__)


class PaymentProcessor:
    def __init__(self):
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    async def create_payment_link(
        self,
        product_name: str,
        amount: int,
        currency: str = 'usd',
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create Stripe payment link for one-time purchase."""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': currency,
                        'product_data': {
                            'name': product_name,
                        },
                        'unit_amount': amount,
                    },
                    'quantity': 1,
                }],
                mode='payment',
                metadata=metadata or {},
                success_url=os.getenv('PAYMENT_SUCCESS_URL'),
                cancel_url=os.getenv('PAYMENT_CANCEL_URL'),
            )
            return {
                'success': True,
                'payment_url': session.url,
                'payment_id': session.id
            }
        except Exception as e:
            logger.error(f"Payment link creation failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_webhook(self, payload: str, sig_header: str) -> Dict:
        """Process Stripe webhook event."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                metadata = session.get('metadata', {})
                return {
                    'success': True,
                    'payment_id': session.id,
                    'amount': session.amount_total,
                    'currency': session.currency,
                    'metadata': metadata,
                    'customer_email': session.customer_details.email if session.customer_details else None
                }
            
            return {'success': True, 'event_type': event['type']}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {str(e)}")
            return {'success': False, 'error': 'Invalid signature'}
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}


async def get_payment_processor() -> PaymentProcessor:
    """Get payment processor instance (for dependency injection)."""
    return PaymentProcessor()
