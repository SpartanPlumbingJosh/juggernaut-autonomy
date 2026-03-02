"""
Payment Handler - Integrates with Stripe and PayPal for payment processing.
Handles webhooks, payment confirmation, and service delivery triggers.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
import paypalrestsdk
from core.database import query_db

# Configure logging
logger = logging.getLogger(__name__)

# Initialize payment gateways
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

class PaymentHandler:
    """Handles payment processing and webhook events."""
    
    def __init__(self):
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    async def create_payment_intent(self, amount: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payment intent with Stripe."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata,
                automatic_payment_methods={"enabled": True},
            )
            return {"success": True, "client_secret": intent.client_secret}
        except stripe.error.StripeError as e:
            logger.error(f"Stripe payment intent creation failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def create_paypal_order(self, amount: str, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a PayPal order."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": amount,
                        "currency": currency
                    },
                    "description": metadata.get("description", "")
                }],
                "redirect_urls": {
                    "return_url": os.getenv("PAYPAL_RETURN_URL"),
                    "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                }
            })
            
            if payment.create():
                return {"success": True, "approval_url": next(link.href for link in payment.links if link.rel == "approval_url")}
            else:
                logger.error(f"PayPal order creation failed: {payment.error}")
                return {"success": False, "error": payment.error}
        except Exception as e:
            logger.error(f"PayPal order creation failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def handle_stripe_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Handle Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                return await self._handle_successful_payment(event['data']['object'])
            elif event['type'] == 'payment_intent.payment_failed':
                return await self._handle_failed_payment(event['data']['object'])
            else:
                return {"success": True, "message": "Unhandled event type"}
        except ValueError as e:
            logger.error(f"Invalid Stripe webhook payload: {str(e)}")
            return {"success": False, "error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid Stripe webhook signature: {str(e)}")
            return {"success": False, "error": "Invalid signature"}
    
    async def _handle_successful_payment(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment."""
        try:
            # Record transaction
            await query_db(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source,
                    metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {payment_intent['amount']},
                    '{payment_intent['currency']}',
                    'stripe',
                    '{json.dumps(payment_intent['metadata'])}'::jsonb,
                    NOW(),
                    NOW()
                )
                """
            )
            
            # Trigger service delivery
            await self._trigger_service_delivery(payment_intent['metadata'])
            
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to handle successful payment: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _trigger_service_delivery(self, metadata: Dict[str, Any]) -> None:
        """Trigger service delivery based on payment metadata."""
        # Implement your service delivery logic here
        pass

    async def _handle_failed_payment(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment."""
        try:
            logger.warning(f"Payment failed: {payment_intent['id']}")
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to handle failed payment: {str(e)}")
            return {"success": False, "error": str(e)}

__all__ = ["PaymentHandler"]
