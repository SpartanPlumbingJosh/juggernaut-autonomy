"""
Payment Processor - Handle stripe/paypal payments and webhooks.
"""

import os
import stripe
from typing import Optional, Dict, Any
from fastapi import Request

# Configure stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

class PaymentProcessor:
    @staticmethod
    async def create_checkout_session(
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create Stripe checkout session"""
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata or {}
            )
            return {
                "session_id": session.id,
                "url": session.url,
                "status": "created"
            }
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    @staticmethod
    async def handle_webhook(request: Request) -> Dict[str, Any]:
        """Process Stripe webhook event"""
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
        except ValueError as e:
            return {"error": "Invalid payload", "status": 400}
        except stripe.error.SignatureVerificationError as e:
            return {"error": "Invalid signature", "status": 400}

        # Handle events
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            return await PaymentProcessor._handle_payment_success(session)
        
        return {"status": "processed"}

    @staticmethod
    async def _handle_payment_success(session: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment"""
        # TODO: Implement database updates and fulfillment
        return {
            "customer": session.get("customer"),
            "amount": session.get("amount_total"),
            "currency": session.get("currency"),
            "status": "success"
        }

payment_processor = PaymentProcessor()
