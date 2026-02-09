"""
Payment Processor - Handle payment gateway integrations, retries, and webhooks.
Supports Stripe, PayPal, and other major gateways.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import stripe
from paypalrestsdk import Payment as PayPalPayment

# Configure logging
logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.gateways = {
            'stripe': self._process_stripe_payment,
            'paypal': self._process_paypal_payment
        }
        self.initialize_gateways()

    def initialize_gateways(self):
        """Initialize payment gateway clients"""
        stripe.api_key = self.config.get('stripe_secret_key')
        paypalrestsdk.configure({
            'mode': self.config.get('paypal_mode', 'sandbox'),
            'client_id': self.config.get('paypal_client_id'),
            'client_secret': self.config.get('paypal_secret')
        })

    async def process_payment(self, payment_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Process payment with retry logic"""
        gateway = payment_data.get('gateway', 'stripe')
        max_retries = self.config.get('payment_retries', 3)
        
        for attempt in range(max_retries):
            try:
                processor = self.gateways.get(gateway)
                if not processor:
                    raise ValueError(f"Unsupported payment gateway: {gateway}")
                
                result = await processor(payment_data)
                if result[0]:
                    return result
                
                logger.warning(f"Payment attempt {attempt + 1} failed, retrying...")
                
            except Exception as e:
                logger.error(f"Payment processing error: {str(e)}")
                if attempt == max_retries - 1:
                    return False, {'error': str(e)}
        
        return False, {'error': 'Max retries reached'}

    async def _process_stripe_payment(self, payment_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Process payment through Stripe"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=payment_data['amount'],
                currency=payment_data['currency'],
                payment_method=payment_data['payment_method'],
                confirmation_method='manual',
                confirm=True,
                metadata=payment_data.get('metadata', {})
            )
            return True, intent
        except stripe.error.StripeError as e:
            return False, {'error': str(e)}

    async def _process_paypal_payment(self, payment_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Process payment through PayPal"""
        try:
            payment = PayPalPayment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": str(payment_data['amount'] / 100),
                        "currency": payment_data['currency']
                    }
                }],
                "redirect_urls": {
                    "return_url": self.config.get('paypal_return_url'),
                    "cancel_url": self.config.get('paypal_cancel_url')
                }
            })
            
            if payment.create():
                return True, payment
            return False, {'error': payment.error}
        except Exception as e:
            return False, {'error': str(e)}

    async def handle_webhook(self, gateway: str, payload: Dict[str, Any]) -> bool:
        """Process payment gateway webhooks"""
        try:
            if gateway == 'stripe':
                event = stripe.Webhook.construct_event(
                    payload,
                    self.config.get('stripe_webhook_secret'),
                    tolerance=300
                )
                return await self._process_stripe_webhook(event)
            elif gateway == 'paypal':
                return await self._process_paypal_webhook(payload)
            return False
        except Exception as e:
            logger.error(f"Webhook processing error: {str(e)}")
            return False

    async def _process_stripe_webhook(self, event: Any) -> bool:
        """Handle Stripe webhook events"""
        event_type = event['type']
        data = event['data']['object']
        
        if event_type == 'payment_intent.succeeded':
            await self._record_payment(data)
            return True
        elif event_type == 'payment_intent.payment_failed':
            await self._handle_failed_payment(data)
            return True
        return False

    async def _process_paypal_webhook(self, payload: Dict[str, Any]) -> bool:
        """Handle PayPal webhook events"""
        event_type = payload.get('event_type')
        resource = payload.get('resource', {})
        
        if event_type == 'PAYMENT.SALE.COMPLETED':
            await self._record_payment(resource)
            return True
        elif event_type == 'PAYMENT.SALE.DENIED':
            await self._handle_failed_payment(resource)
            return True
        return False

    async def _record_payment(self, payment_data: Dict[str, Any]) -> None:
        """Record successful payment"""
        # Implement payment recording logic
        pass

    async def _handle_failed_payment(self, payment_data: Dict[str, Any]) -> None:
        """Handle failed payment"""
        # Implement failed payment handling
        pass
