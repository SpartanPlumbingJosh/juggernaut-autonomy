"""
Payment Service - Handles payment processing and fulfillment.
"""
import os
import stripe
import paypalrestsdk
from typing import Dict, Any, Optional
from datetime import datetime

# Configure payment providers
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_SECRET')
})

class PaymentService:
    @staticmethod
    async def create_payment_intent(amount: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata,
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            return {
                'success': True,
                'client_secret': intent.client_secret,
                'payment_id': intent.id
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': 'stripe_error'
            }

    @staticmethod
    async def create_paypal_order(amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create PayPal order."""
        try:
            order = paypalrestsdk.Order({
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": currency,
                        "value": str(amount)
                    },
                    "custom_id": metadata.get('product_id', ''),
                    "description": metadata.get('description', '')
                }],
                "application_context": {
                    "return_url": os.getenv('PAYPAL_RETURN_URL'),
                    "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                }
            })
            
            if order.create():
                return {
                    'success': True,
                    'order_id': order.id,
                    'approval_url': next(link.href for link in order.links if link.rel == 'approve')
                }
            return {
                'success': False,
                'error': order.error,
                'error_type': 'paypal_error'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': 'paypal_error'
            }

    @staticmethod
    async def fulfill_payment(payment_id: str, provider: str) -> Dict[str, Any]:
        """Complete payment fulfillment."""
        try:
            if provider == 'stripe':
                intent = stripe.PaymentIntent.retrieve(payment_id)
                if intent.status == 'succeeded':
                    return {
                        'success': True,
                        'amount': intent.amount,
                        'currency': intent.currency,
                        'metadata': intent.metadata
                    }
            elif provider == 'paypal':
                order = paypalrestsdk.Order.find(payment_id)
                if order.capture():
                    return {
                        'success': True,
                        'amount': float(order.purchase_units[0].amount.value),
                        'currency': order.purchase_units[0].amount.currency_code,
                        'metadata': {
                            'custom_id': order.purchase_units[0].custom_id
                        }
                    }
            return {
                'success': False,
                'error': 'Payment not completed',
                'error_type': 'payment_not_completed'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': 'fulfillment_error'
            }
