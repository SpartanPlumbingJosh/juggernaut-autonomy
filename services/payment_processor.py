import os
import stripe
import paypalrestsdk
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum, auto

class PaymentProvider(Enum):
    STRIPE = auto()
    PAYPAL = auto()

class PaymentProcessor:
    def __init__(self):
        self.stripe_api_key = os.getenv('STRIPE_API_KEY')
        self.paypal_config = {
            'mode': os.getenv('PAYPAL_MODE', 'sandbox'),
            'client_id': os.getenv('PAYPAL_CLIENT_ID'),
            'client_secret': os.getenv('PAYPAL_CLIENT_SECRET')
        }
        
        stripe.api_key = self.stripe_api_key
        paypalrestsdk.configure(self.paypal_config)

    async def create_payment_intent(
        self,
        amount_cents: int,
        currency: str,
        provider: PaymentProvider,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if provider == PaymentProvider.STRIPE:
            return await self._create_stripe_payment(amount_cents, currency, metadata)
        else:
            return await self._create_paypal_payment(amount_cents, currency, metadata)

    async def _create_stripe_payment(self, amount_cents: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata or {},
                automatic_payment_methods={
                    'enabled': True,
                }
            )
            return {
                'provider': 'stripe',
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'status': intent.status
            }
        except Exception as e:
            raise Exception(f"Stripe payment failed: {str(e)}")

    async def _create_paypal_payment(self, amount_cents: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount_cents/100:.2f}",
                        "currency": currency.upper()
                    },
                    "description": metadata.get('description', '')
                }],
                "redirect_urls": {
                    "return_url": os.getenv('PAYPAL_RETURN_URL'),
                    "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                }
            })
            
            if payment.create():
                return {
                    'provider': 'paypal',
                    'approval_url': next(link.href for link in payment.links if link.rel == 'approval_url'),
                    'payment_id': payment.id,
                    'status': payment.state
                }
            else:
                raise Exception(payment.error)
        except Exception as e:
            raise Exception(f"PayPal payment failed: {str(e)}")

    async def verify_payment(self, payment_id: str, provider: PaymentProvider) -> Dict[str, Any]:
        if provider == PaymentProvider.STRIPE:
            return await self._verify_stripe_payment(payment_id)
        else:
            return await self._verify_paypal_payment(payment_id)

    async def _verify_stripe_payment(self, payment_id: str) -> Dict[str, Any]:
        try:
            intent = stripe.PaymentIntent.retrieve(payment_id)
            return {
                'success': intent.status == 'succeeded',
                'status': intent.status,
                'amount': intent.amount,
                'currency': intent.currency,
                'metadata': intent.metadata
            }
        except Exception as e:
            raise Exception(f"Stripe verification failed: {str(e)}")

    async def _verify_paypal_payment(self, payment_id: str) -> Dict[str, Any]:
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            if payment.success():
                return {
                    'success': payment.state == 'approved',
                    'status': payment.state,
                    'amount': payment.transactions[0].amount.total,
                    'currency': payment.transactions[0].amount.currency,
                    'metadata': {'description': payment.transactions[0].description}
                }
            else:
                raise Exception(payment.error)
        except Exception as e:
            raise Exception(f"PayPal verification failed: {str(e)}")
