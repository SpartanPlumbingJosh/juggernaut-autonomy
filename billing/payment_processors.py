"""
Payment processor abstraction layer supporting multiple providers.
"""

from typing import Dict, Optional
import stripe
import paypalrestsdk

class PaymentProcessor:
    def __init__(self, provider: str, api_key: str):
        self.provider = provider
        if provider == 'stripe':
            stripe.api_key = api_key
        elif provider == 'paypal':
            paypalrestsdk.configure({
                "mode": "live",
                "client_id": api_key
            })

    async def charge(self, customer_id: str, amount: float, 
                    currency: str, payment_method_id: str) -> Dict:
        """Process payment through configured provider"""
        if self.provider == 'stripe':
            return await self._process_stripe_payment(
                customer_id, amount, currency, payment_method_id
            )
        elif self.provider == 'paypal':
            return await self._process_paypal_payment(
                customer_id, amount, currency, payment_method_id
            )
        else:
            raise ValueError(f"Unsupported payment provider: {self.provider}")

    async def _process_stripe_payment(self, customer_id: str, amount: float,
                                    currency: str, payment_method_id: str) -> Dict:
        """Process payment via Stripe"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # convert to cents
                currency=currency.lower(),
                customer=customer_id,
                payment_method=payment_method_id,
                confirm=True,
                off_session=True
            )
            return {
                'success': True,
                'transaction_id': intent.id,
                'amount': amount,
                'currency': currency
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
                'decline_code': getattr(e, 'decline_code', None)
            }

    async def _process_paypal_payment(self, customer_id: str, amount: float,
                                    currency: str, payment_method_id: str) -> Dict:
        """Process payment via PayPal"""
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {
                "payment_method": "credit_card",
                "funding_instruments": [{
                    "credit_card_token": {
                        "credit_card_id": payment_method_id
                    }
                }]
            },
            "transactions": [{
                "amount": {
                    "total": str(amount),
                    "currency": currency
                }
            }]
        })

        if payment.create():
            return {
                'success': True,
                'transaction_id': payment.id,
                'amount': amount,
                'currency': currency
            }
        else:
            return {
                'success': False,
                'error': payment.error
            }
