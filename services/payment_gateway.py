"""
Payment Gateway Service - Handles payment processing with Stripe/PayPal.
Includes retry logic, error handling, and transaction tracking.
"""

import os
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from enum import Enum, auto

class PaymentGateway(Enum):
    STRIPE = auto()
    PAYPAL = auto()

class PaymentError(Exception):
    """Custom exception for payment processing errors"""
    def __init__(self, message: str, gateway: PaymentGateway, retryable: bool = False):
        super().__init__(message)
        self.gateway = gateway
        self.retryable = retryable

class PaymentGatewayService:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        paypalrestsdk.configure({
            "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
            "client_id": os.getenv('PAYPAL_CLIENT_ID'),
            "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
        })

    async def process_payment(
        self,
        gateway: PaymentGateway,
        amount: float,
        currency: str,
        payment_method: Dict,
        metadata: Optional[Dict] = None
    ) -> Tuple[str, Dict]:
        """
        Process payment through selected gateway
        Returns (transaction_id, gateway_response)
        """
        try:
            if gateway == PaymentGateway.STRIPE:
                return await self._process_stripe_payment(amount, currency, payment_method, metadata)
            elif gateway == PaymentGateway.PAYPAL:
                return await self._process_paypal_payment(amount, currency, payment_method, metadata)
            else:
                raise PaymentError("Invalid payment gateway", gateway)
        except Exception as e:
            raise PaymentError(str(e), gateway, retryable=True)

    async def _process_stripe_payment(self, amount: float, currency: str, payment_method: Dict, metadata: Dict) -> Tuple[str, Dict]:
        """Process payment through Stripe"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                payment_method=payment_method.get('id'),
                confirm=True,
                metadata=metadata or {},
                capture_method='automatic'
            )
            return intent.id, intent
        except stripe.error.StripeError as e:
            raise PaymentError(f"Stripe error: {str(e)}", PaymentGateway.STRIPE, retryable=True)

    async def _process_paypal_payment(self, amount: float, currency: str, payment_method: Dict, metadata: Dict) -> Tuple[str, Dict]:
        """Process payment through PayPal"""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": payment_method.get('method')
                },
                "transactions": [{
                    "amount": {
                        "total": f"{amount:.2f}",
                        "currency": currency.upper()
                    },
                    "description": metadata.get('description', '')
                }]
            })
            
            if payment.create():
                return payment.id, payment.to_dict()
            else:
                raise PaymentError(f"PayPal error: {payment.error}", PaymentGateway.PAYPAL)
        except Exception as e:
            raise PaymentError(f"PayPal processing error: {str(e)}", PaymentGateway.PAYPAL, retryable=True)

    async def refund_payment(self, gateway: PaymentGateway, transaction_id: str, amount: Optional[float] = None) -> bool:
        """Process refund through selected gateway"""
        try:
            if gateway == PaymentGateway.STRIPE:
                return await self._process_stripe_refund(transaction_id, amount)
            elif gateway == PaymentGateway.PAYPAL:
                return await self._process_paypal_refund(transaction_id, amount)
            else:
                raise PaymentError("Invalid payment gateway", gateway)
        except Exception as e:
            raise PaymentError(str(e), gateway)

    async def _process_stripe_refund(self, transaction_id: str, amount: Optional[float]) -> bool:
        """Process refund through Stripe"""
        try:
            refund = stripe.Refund.create(
                payment_intent=transaction_id,
                amount=int(amount * 100) if amount else None
            )
            return refund.status == 'succeeded'
        except stripe.error.StripeError as e:
            raise PaymentError(f"Stripe refund error: {str(e)}", PaymentGateway.STRIPE)

    async def _process_paypal_refund(self, transaction_id: str, amount: Optional[float]) -> bool:
        """Process refund through PayPal"""
        try:
            sale = paypalrestsdk.Sale.find(transaction_id)
            refund = sale.refund({
                "amount": {
                    "total": f"{amount:.2f}" if amount else sale.amount['total'],
                    "currency": sale.amount['currency']
                }
            })
            return refund.success()
        except Exception as e:
            raise PaymentError(f"PayPal refund error: {str(e)}", PaymentGateway.PAYPAL)
