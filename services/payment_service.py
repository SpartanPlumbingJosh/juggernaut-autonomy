"""
Payment processing service with Stripe/PayPal integration.
Handles all payment operations with fraud detection and rate limiting.
"""
import os
import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

import stripe
import paypalrestsdk
from fastapi import HTTPException, status, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

# Configure rate limiting
limiter = Limiter(key_func=get_remote_address)

# Initialize payment providers
stripe.api_key = os.getenv('STRIPE_API_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_SECRET')
})

class PaymentService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.fraud_rules = {
            'high_amount': 10000,  # $100 in cents
            'rapid_attempts': 5,
            'time_window': 60  # 1 minute
        }
        self.attempts = {}  # Track payment attempts for fraud detection

    @limiter.limit("10/minute")
    async def create_payment_intent(
        self,
        amount: int,
        currency: str = 'usd',
        payment_method: str = 'stripe',
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a payment intent with fraud checks."""
        try:
            # Fraud detection checks
            client_ip = get_remote_address()
            now = time.time()
            
            # Track attempts
            if client_ip not in self.attempts:
                self.attempts[client_ip] = {'count': 0, 'last_attempt': 0}
            
            # Check for rapid attempts
            if (now - self.attempts[client_ip]['last_attempt']) < self.fraud_rules['time_window']:
                self.attempts[client_ip]['count'] += 1
                if self.attempts[client_ip]['count'] > self.fraud_rules['rapid_attempts']:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many payment attempts"
                    )
            else:
                self.attempts[client_ip] = {'count': 1, 'last_attempt': now}
            
            # Check for high amount
            if amount > self.fraud_rules['high_amount']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="High amount requires manual review"
                )

            # Process payment based on method
            if payment_method == 'stripe':
                intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency=currency,
                    metadata=metadata or {},
                    payment_method_types=['card']
                )
                return {
                    'client_secret': intent.client_secret,
                    'payment_id': intent.id,
                    'status': intent.status
                }
            elif payment_method == 'paypal':
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": str(amount / 100),
                            "currency": currency.upper()
                        }
                    }],
                    "redirect_urls": {
                        "return_url": os.getenv('PAYPAL_RETURN_URL'),
                        "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                    }
                })
                if payment.create():
                    return {
                        'approval_url': next(
                            link.href for link in payment.links 
                            if link.method == "REDIRECT" and link.rel == "approval_url"
                        ),
                        'payment_id': payment.id,
                        'status': payment.state
                    }
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=payment.error
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unsupported payment method"
                )
        except Exception as e:
            self.logger.error(f"Payment processing failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment processing failed"
            )

    async def handle_webhook(self, payload: Dict[str, Any], sig_header: str) -> bool:
        """Process payment webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
            )
            
            if event['type'] == 'payment_intent.succeeded':
                # Record successful payment
                payment_intent = event['data']['object']
                await self.record_payment(
                    payment_id=payment_intent['id'],
                    amount=payment_intent['amount'],
                    currency=payment_intent['currency'],
                    status='completed',
                    metadata=payment_intent.get('metadata', {})
                )
                return True
            
            return False
        except Exception as e:
            self.logger.error(f"Webhook processing failed: {str(e)}")
            return False

    async def record_payment(self, **kwargs):
        """Record payment in database."""
        # Implementation would record to database
        pass
