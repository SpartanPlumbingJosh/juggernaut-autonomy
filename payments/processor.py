"""
Payment processor module integrating with Stripe for PCI-compliant payments.
Handles secure payment authorization, settlements and refunds.
"""
import os
import stripe
from datetime import datetime
from typing import Dict, Optional

class PaymentProcessor:
    def __init__(self, api_key: str):
        """
        Initialize Stripe payment processor.
        Requires STRIPE_SECRET_KEY environment variable.
        """
        stripe.api_key = api_key or os.getenv('STRIPE_SECRET_KEY')
        if not stripe.api_key:
            raise ValueError("STRIPE_SECRET_KEY must be configured")

    async def create_payment_intent(
        self,
        amount: int,
        currency: str,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create a payment intent with PCI-compliant tokenization."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                metadata=metadata or {},
                setup_future_usage='off_session' if customer_id else None,
                payment_method_types=['card'],
            )
            return {
                'status': 'requires_payment_method',
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id
            }
        except Exception as e:
            return {'error': str(e), 'status': 'failed'}

    async def confirm_payment(self, payment_intent_id: str) -> Dict:
        """Confirm a payment intent after customer completes authentication."""
        try:
            intent = stripe.PaymentIntent.confirm(payment_intent_id)
            return self._format_payment_response(intent)
        except Exception as e:
            return {'error': str(e), 'status': 'failed'}

    def _format_payment_response(self, intent) -> Dict:
        """Standardize payment intent response format."""
        return {
            'status': intent.status,
            'amount': intent.amount,
            'currency': intent.currency,
            'payment_method': intent.payment_method,
            'receipt_url': intent.charges.data[0].receipt_url if intent.charges.data else None,
            'paid_at': datetime.fromtimestamp(intent.charges.data[0].created).isoformat() if intent.charges.data else None
        }
