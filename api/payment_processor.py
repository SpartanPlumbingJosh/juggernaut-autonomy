import stripe
import paypalrestsdk
from datetime import datetime
from typing import Dict, Optional

class PaymentProcessor:
    def __init__(self, stripe_key: str, paypal_config: Dict[str, str]):
        stripe.api_key = stripe_key
        paypalrestsdk.configure(paypal_config)
        
    def create_payment(self, amount: float, currency: str, payment_method: str, 
                      customer_info: Dict[str, str]) -> Dict[str, Any]:
        """Process payment through Stripe or PayPal"""
        try:
            if payment_method == 'stripe':
                intent = stripe.PaymentIntent.create(
                    amount=int(amount * 100),  # Convert to cents
                    currency=currency.lower(),
                    payment_method_types=['card'],
                    receipt_email=customer_info.get('email'),
                    metadata={
                        'customer_id': customer_info.get('id'),
                        'product': customer_info.get('product')
                    }
                )
                return {
                    'success': True,
                    'payment_id': intent.id,
                    'client_secret': intent.client_secret,
                    'provider': 'stripe'
                }
            elif payment_method == 'paypal':
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {
                        "payment_method": "paypal"
                    },
                    "transactions": [{
                        "amount": {
                            "total": str(amount),
                            "currency": currency
                        },
                        "description": f"Purchase of {customer_info.get('product')}"
                    }],
                    "redirect_urls": {
                        "return_url": "https://example.com/success",
                        "cancel_url": "https://example.com/cancel"
                    }
                })
                if payment.create():
                    return {
                        'success': True,
                        'payment_id': payment.id,
                        'approval_url': next(link.href for link in payment.links if link.rel == "approval_url"),
                        'provider': 'paypal'
                    }
            return {'success': False, 'error': 'Invalid payment method'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
