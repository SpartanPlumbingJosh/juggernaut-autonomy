"""
Payment gateway integration supporting multiple providers.
Handles payment processing, refunds, and subscription management.
"""

import stripe
from typing import Dict, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PaymentResult:
    success: bool
    payment_id: Optional[str] = None
    error: Optional[str] = None
    requires_action: bool = False
    client_secret: Optional[str] = None

class PaymentGateway:
    def __init__(self, stripe_api_key: str):
        self.stripe_api_key = stripe_api_key
        stripe.api_key = stripe_api_key
        
    def create_payment_intent(self, amount: int, currency: str = "usd", metadata: Optional[Dict] = None) -> PaymentResult:
        """Create a payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            
            return PaymentResult(
                success=True,
                payment_id=intent.id,
                requires_action=intent.status == 'requires_action',
                client_secret=intent.client_secret
            )
        except stripe.error.StripeError as e:
            logger.error(f"Payment failed: {str(e)}")
            return PaymentResult(
                success=False,
                error=str(e)
            )
            
    def confirm_payment(self, payment_id: str) -> PaymentResult:
        """Confirm a payment."""
        try:
            intent = stripe.PaymentIntent.confirm(payment_id)
            return PaymentResult(
                success=intent.status == 'succeeded',
                payment_id=intent.id
            )
        except stripe.error.StripeError as e:
            logger.error(f"Payment confirmation failed: {str(e)}")
            return PaymentResult(
                success=False,
                error=str(e)
            )
            
    def create_subscription(self, customer_id: str, price_id: str) -> PaymentResult:
        """Create a subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{
                    'price': price_id,
                }],
                expand=['latest_invoice.payment_intent']
            )
            
            return PaymentResult(
                success=True,
                payment_id=subscription.id
            )
        except stripe.error.StripeError as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            return PaymentResult(
                success=False,
                error=str(e)
            )
