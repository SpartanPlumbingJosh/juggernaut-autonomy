"""
Stripe payment processor integration.
Handles all Stripe-specific payment operations.
"""
import stripe
from typing import Dict, Optional
from datetime import datetime

stripe.api_version = '2023-08-16'

class StripeProcessor:
    def __init__(self, api_key: str):
        self.client = stripe
        self.client.api_key = api_key
        
    async def create_charge(self, amount: int, currency: str = 'USD', 
                          customer_id: Optional[str] = None,
                          description: str = "") -> Dict:
        """Create a Stripe charge."""
        try:
            intent = self.client.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                description=description,
                confirm=True
            )
            return {
                'success': True,
                'charge_id': intent.id,
                'amount': intent.amount,
                'receipt_url': intent.charges.data[0].receipt_url
            }
        except stripe.error.StripeError as e:
            return {'success': False, 'error': str(e)}

    async def create_subscription(self, customer_id: str, plan_id: str,
                                payment_method_id: str) -> Dict:
        """Create Stripe subscription."""
        try:
            subscription = self.client.Subscription.create(
                customer=customer_id,
                items=[{'price': plan_id}],
                default_payment_method=payment_method_id,
                expand=['latest_invoice.payment_intent']
            )
            return {
                'success': True,
                'subscription_id': subscription.id,
                'status': subscription.status
            }
        except stripe.error.StripeError as e:
            return {'success': False, 'error': str(e)}

    def verify_webhook(self, payload: bytes, sig_header: str, endpoint_secret: str) -> bool:
        """Verify Stripe webhook signature."""
        try:
            event = self.client.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
            return event
        except ValueError as e:
            return False
        except stripe.error.SignatureVerificationError as e:
            return False
