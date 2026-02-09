"""
Payment Processor - Handles Stripe/PayPal integrations, webhooks, and automated fulfillment.
"""
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import stripe
import paypalrestsdk
from core.database import query_db

# Configuration
STRIPE_API_KEY = "sk_test_..."  # Should be from environment variables
PAYPAL_MODE = "sandbox"  # or "live"
PAYPAL_CLIENT_ID = "..."  # Should be from environment variables
PAYPAL_SECRET = "..."  # Should be from environment variables

# Initialize payment gateways
stripe.api_key = STRIPE_API_KEY
paypalrestsdk.configure({
    "mode": PAYPAL_MODE,
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_SECRET
})

class PaymentProcessor:
    """Handles payment processing and fulfillment."""
    
    def __init__(self):
        self.retry_attempts = 3
        self.retry_delay = 1  # seconds

    async def create_stripe_payment_intent(
        self, 
        amount_cents: int,
        currency: str,
        metadata: Dict[str, Any],
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a Stripe PaymentIntent with idempotency."""
        idempotency_key = idempotency_key or str(uuid.uuid4())
        
        for attempt in range(self.retry_attempts):
            try:
                intent = stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=currency.lower(),
                    metadata=metadata,
                    idempotency_key=idempotency_key
                )
                return {
                    "success": True,
                    "client_secret": intent.client_secret,
                    "payment_id": intent.id
                }
            except stripe.error.StripeError as e:
                if attempt == self.retry_attempts - 1:
                    return {"success": False, "error": str(e)}
                time.sleep(self.retry_delay)

    async def create_paypal_order(
        self,
        amount_cents: int,
        currency: str,
        metadata: Dict[str, Any],
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a PayPal order with idempotency."""
        idempotency_key = idempotency_key or str(uuid.uuid4())
        amount = round(amount_cents / 100, 2)
        
        for attempt in range(self.retry_attempts):
            try:
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": str(amount),
                            "currency": currency.upper()
                        },
                        "description": metadata.get("description", ""),
                        "custom": idempotency_key
                    }],
                    "redirect_urls": {
                        "return_url": "https://example.com/success",
                        "cancel_url": "https://example.com/cancel"
                    }
                })
                
                if payment.create():
                    return {
                        "success": True,
                        "approval_url": next(
                            link.href for link in payment.links 
                            if link.method == "REDIRECT" and link.rel == "approval_url"
                        ),
                        "payment_id": payment.id
                    }
                return {"success": False, "error": payment.error}
            except Exception as e:
                if attempt == self.retry_attempts - 1:
                    return {"success": False, "error": str(e)}
                time.sleep(self.retry_delay)

    async def handle_stripe_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, "your_stripe_webhook_signing_secret"
            )
            
            if event.type == "payment_intent.succeeded":
                intent = event.data.object
                await self._fulfill_order(
                    "stripe",
                    intent.id,
                    intent.amount,
                    intent.currency,
                    intent.metadata
                )
            
            return {"success": True}
        except ValueError as e:
            return {"success": False, "error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            return {"success": False, "error": "Invalid signature"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_paypal_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process PayPal webhook events."""
        try:
            if payload.get("event_type") == "PAYMENT.SALE.COMPLETED":
                resource = payload.get("resource", {})
                await self._fulfill_order(
                    "paypal",
                    resource.get("id"),
                    int(float(resource.get("amount", {}).get("total", 0)) * 100),
                    resource.get("amount", {}).get("currency", "USD"),
                    {"custom": resource.get("custom", "")}
                )
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _fulfill_order(
        self,
        gateway: str,
        transaction_id: str,
        amount_cents: int,
        currency: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Process and fulfill an order."""
        # Check for duplicate processing
        existing = await query_db(
            f"""
            SELECT id FROM revenue_events 
            WHERE metadata->>'transaction_id' = '{transaction_id}'
            LIMIT 1
            """
        )
        if existing.get("rows"):
            return

        # Record revenue event
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                '{currency}',
                '{gateway}',
                '{json.dumps({"transaction_id": transaction_id, **metadata})}'::jsonb,
                NOW(),
                NOW()
            )
            """
        )

        # TODO: Add your product/service fulfillment logic here
        # This could be:
        # - Granting access to digital products
        # - Triggering service delivery
        # - Adding to a subscription
        # - Sending confirmation emails
        # etc.

    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        metadata: Dict[str, Any],
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a subscription with retry logic."""
        idempotency_key = idempotency_key or str(uuid.uuid4())
        
        for attempt in range(self.retry_attempts):
            try:
                subscription = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{"plan": plan_id}],
                    metadata=metadata,
                    idempotency_key=idempotency_key
                )
                return {
                    "success": True,
                    "subscription_id": subscription.id,
                    "status": subscription.status
                }
            except stripe.error.StripeError as e:
                if attempt == self.retry_attempts - 1:
                    return {"success": False, "error": str(e)}
                time.sleep(self.retry_delay)

    async def cancel_subscription(
        self,
        subscription_id: str,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cancel a subscription with retry logic."""
        idempotency_key = idempotency_key or str(uuid.uuid4())
        
        for attempt in range(self.retry_attempts):
            try:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True,
                    idempotency_key=idempotency_key
                )
                return {
                    "success": True,
                    "subscription_id": subscription.id,
                    "status": subscription.status
                }
            except stripe.error.StripeError as e:
                if attempt == self.retry_attempts - 1:
                    return {"success": False, "error": str(e)}
                time.sleep(self.retry_delay)

    async def process_refund(
        self,
        payment_id: str,
        amount_cents: int,
        reason: str,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a refund with retry logic."""
        idempotency_key = idempotency_key or str(uuid.uuid4())
        
        for attempt in range(self.retry_attempts):
            try:
                refund = stripe.Refund.create(
                    payment_intent=payment_id,
                    amount=amount_cents,
                    reason=reason,
                    idempotency_key=idempotency_key
                )
                return {
                    "success": True,
                    "refund_id": refund.id,
                    "status": refund.status
                }
            except stripe.error.StripeError as e:
                if attempt == self.retry_attempts - 1:
                    return {"success": False, "error": str(e)}
                time.sleep(self.retry_delay)
