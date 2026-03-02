import os
import stripe
import logging
from typing import Optional, Dict, Any
from datetime import datetime

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

class PaymentProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    async def create_checkout_session(
        self, 
        product_id: str,
        price: int,  # in cents
        currency: str = 'usd',
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create Stripe checkout session"""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': currency,
                        'product_data': {
                            'name': product_id,
                        },
                        'unit_amount': price,
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=os.getenv('STRIPE_SUCCESS_URL'),
                cancel_url=os.getenv('STRIPE_CANCEL_URL'),
                metadata=metadata or {},
            )
            return {'success': True, 'session_id': session.id, 'url': session.url}
        except Exception as e:
            self.logger.error(f"Payment session failed: {str(e)}")
            return {'error': str(e)}

    async def record_transaction(
        self,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record payment transaction in DB"""
        event_type = event_data['type']
        
        try:
            tx = {
                'payment_id': event_data['id'],
                'amount': event_data['amount'],
                'currency': event_data['currency'],
                'status': event_data.get('status', 'completed'),
                'recorded_at': datetime.utcnow(),
                'metadata': event_data.get('metadata', {}),
                'type': event_type
            }
            
            # Save tx to database...
            return {'success': True}
            
        except Exception as e:
            self.logger.error(f"Transaction recording failed: {str(e)}")
            return {'error': str(e)}
