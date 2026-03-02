import os
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Optional

# Initialize payment processors
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
})

class PaymentProcessor:
    @staticmethod
    async def create_payment(amount: float, currency: str, payment_method: str, metadata: Dict) -> Dict:
        """Create payment using selected processor"""
        amount_cents = int(amount * 100)  # Convert to cents
        
        if payment_method == 'stripe':
            try:
                payment_intent = stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=currency,
                    metadata=metadata
                )
                return {
                    'success': True,
                    'payment_id': payment_intent.id,
                    'client_secret': payment_intent.client_secret,
                    'processor': 'stripe'
                }
            except stripe.error.StripeError as e:
                return {'success': False, 'error': str(e)}
                
        elif payment_method == 'paypal':
            try:
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": f"{amount:.2f}",
                            "currency": currency
                        },
                        "description": metadata.get('description', '')
                    }],
                    "redirect_urls": {
                        "return_url": metadata.get('return_url', ''),
                        "cancel_url": metadata.get('cancel_url', '')
                    }
                })
                
                if payment.create():
                    return {
                        'success': True,
                        'payment_id': payment.id,
                        'approval_url': next(link.href for link in payment.links if link.method == "REDIRECT"),
                        'processor': 'paypal'
                    }
                return {'success': False, 'error': payment.error}
            except Exception as e:
                return {'success': False, 'error': str(e)}
                
        return {'success': False, 'error': 'Invalid payment method'}

    @staticmethod
    async def confirm_payment(payment_id: str, processor: str) -> Dict:
        """Confirm payment completion"""
        if processor == 'stripe':
            try:
                payment_intent = stripe.PaymentIntent.retrieve(payment_id)
                if payment_intent.status == 'succeeded':
                    return {'success': True, 'status': 'completed'}
                return {'success': False, 'status': payment_intent.status}
            except stripe.error.StripeError as e:
                return {'success': False, 'error': str(e)}
                
        elif processor == 'paypal':
            try:
                payment = paypalrestsdk.Payment.find(payment_id)
                if payment.state == 'approved':
                    return {'success': True, 'status': 'completed'}
                return {'success': False, 'status': payment.state}
            except Exception as e:
                return {'success': False, 'error': str(e)}
                
        return {'success': False, 'error': 'Invalid processor'}
