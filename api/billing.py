"""
Billing Core - Payment processing and subscription management
"""
import os
import stripe
from datetime import datetime, timezone
from typing import Dict, Any, Optional

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

class BillingProcessor:
    def __init__(self):
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create recurring subscription"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            return {
                'subscription_id': subscription.id,
                'client_secret': subscription.latest_invoice.payment_intent.client_secret,
                'status': subscription.status
            }
        except Exception as e:
            return {'error': str(e)}

    def process_payment(self, payment_method_id: str, amount: int, currency: str = 'usd') -> Dict[str, Any]:
        """Process one-time payment"""
        try:
            payment = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                payment_method=payment_method_id,
                confirm=True,
                metadata={'integration_check': 'accept_a_payment'}
            )
            return {
                'payment_id': payment.id,
                'amount': payment.amount,
                'status': payment.status
            }
        except Exception as e:
            return {'error': str(e)}

    def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret)
            
            # Handle payment succeeded
            if event['type'] == 'payment_intent.succeeded':
                payment = event['data']['object']
                self._record_payment(payment)
            
            return {'success': True}
        except ValueError as e:
            return {'error': str(e)}
