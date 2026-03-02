import stripe
from typing import Dict, Any, Optional
import os
from datetime import datetime, timezone

class StripePaymentProcessor:
    def __init__(self):
        self.stripe_api_key = os.getenv('STRIPE_SECRET_KEY')
        stripe.api_key = self.stripe_api_key

    async def create_payment_intent(self, amount: int, currency: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a Stripe PaymentIntent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            return {
                'success': True,
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def record_payment_event(self, payment_intent_id: str, tracked_experiment_id: Optional[str] = None) -> Dict[str, Any]:
        """Record a successful payment in revenue_events."""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if intent.status == 'succeeded':
                return {
                    'amount_cents': intent.amount,
                    'currency': intent.currency,
                    'payment_intent_id': payment_intent_id,
                    'metadata': intent.metadata or {},
                    'customer_id': intent.customer,
                    'payment_method': intent.payment_method,
                    'timestamp': datetime.fromtimestamp(intent.created, tz=timezone.utc).isoformat(),
                    'tracked_experiment_id': tracked_experiment_id
                }
            return {'success': False, 'error': f'Payment not succeeded - status: {intent.status}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
