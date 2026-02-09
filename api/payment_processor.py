"""
Stripe/PayPal payment processor with webhooks and subscription handling.

Handles:
- One-time payments
- Recurring subscriptions
- Webhook event processing
- Failed payment recovery
"""

import os
from datetime import datetime
import stripe
import paypalrestsdk
from typing import Dict, Any, Optional
from fastapi import HTTPException

# Configure payment processors
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_SECRET')
})

class PaymentProcessor:
    def __init__(self):
        self.webhook_handlers = {
            'stripe': self._handle_stripe_webhook,
            'paypal': self._handle_paypal_webhook
        }

    async def create_checkout_session(self, 
                                    amount_cents: int, 
                                    currency: str,
                                    product_id: str,
                                    customer_email: str,
                                    metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payment checkout session"""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': currency.lower(),
                        'product_data': {
                            'name': "Digital Product",
                        },
                        'unit_amount': amount_cents,
                    },
                    'quantity': 1,
                }],
                mode='payment',
                customer_email=customer_email,
                metadata=metadata,
                success_url=f"{os.getenv('CHECKOUT_SUCCESS_URL')}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{os.getenv('CHECKOUT_CANCEL_URL')}?session_id={{CHECKOUT_SESSION_ID}}",
                automatic_tax={'enabled': True},
            )
            return {"success": True, "session_url": session.url, "session_id": session.id}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def create_subscription(self,
                                plan_id: str,
                                customer_email: str,
                                metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create recurring subscription"""
        try:
            customer = stripe.Customer.create(email=customer_email)
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{'price': plan_id}],
                metadata=metadata,
                payment_behavior='default_incomplete',
            )
            
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                subscription=subscription.id,
                customer=customer.id,
                success_url=f"{os.getenv('SUBSCRIPTION_SUCCESS_URL')}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{os.getenv('SUBSCRIPTION_CANCEL_URL')}?session_id={{CHECKOUT_SESSION_ID}}",
            )
            return {"success": True, "session_url": session.url}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def handle_webhook(self, provider: str, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process webhook events from payment providers"""
        try:
            handler = self.webhook_handlers.get(provider.lower())
            if not handler:
                raise HTTPException(status_code=400, detail="Invalid payment provider")
            
            event = handler(payload, sig_header)
            return await self._process_webhook_event(event)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Additional methods would include:
    # - _handle_stripe_webhook
    # - _handle_paypal_webhook  
    # - _process_webhook_event
    # - _handle_payment_success
    # - _handle_payment_failure
    # - _handle_subscription_update
    # - Refund processing
    # And other payment-related operations
