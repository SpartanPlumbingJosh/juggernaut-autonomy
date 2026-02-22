"""
Payment Processor - Handles payment integrations and webhooks.

Supports:
- Stripe
- PayPal
- Manual payments
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import stripe
from paypalrestsdk import Payment

from core.database import query_db

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self, stripe_api_key: str, paypal_client_id: str, paypal_secret: str):
        self.stripe_api_key = stripe_api_key
        self.paypal_client_id = paypal_client_id
        self.paypal_secret = paypal_secret
        
        stripe.api_key = stripe_api_key
        Payment.configure({
            "mode": "live",
            "client_id": paypal_client_id,
            "client_secret": paypal_secret
        })

    async def create_stripe_payment_intent(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe PaymentIntent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                metadata=metadata,
                automatic_payment_methods={"enabled": True}
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            logger.error(f"Stripe payment intent creation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_paypal_payment(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a PayPal payment."""
        try:
            payment = Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount:.2f}",
                        "currency": currency.upper()
                    },
                    "description": metadata.get("description", "")
                }],
                "redirect_urls": {
                    "return_url": metadata.get("return_url", ""),
                    "cancel_url": metadata.get("cancel_url", "")
                }
            })
            
            if payment.create():
                return {"success": True, "approval_url": payment.links[1].href}
            return {"success": False, "error": "PayPal payment creation failed"}
        except Exception as e:
            logger.error(f"PayPal payment creation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_stripe_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Tuple[int, Dict[str, Any]]:
        """Process Stripe webhook event."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event.type == "payment_intent.succeeded":
                payment_intent = event.data.object
                await self._record_transaction(
                    amount=payment_intent.amount / 100,
                    currency=payment_intent.currency,
                    payment_method="stripe",
                    payment_id=payment_intent.id,
                    metadata=payment_intent.metadata
                )
                return 200, {"success": True}
                
            return 200, {"success": True, "message": "Event not processed"}
        except Exception as e:
            logger.error(f"Stripe webhook processing failed: {str(e)}")
            return 400, {"success": False, "error": str(e)}

    async def handle_paypal_webhook(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """Process PayPal webhook event."""
        try:
            if payload.get("event_type") == "PAYMENT.SALE.COMPLETED":
                sale = payload.get("resource", {})
                await self._record_transaction(
                    amount=float(sale.get("amount", {}).get("total", 0)),
                    currency=sale.get("amount", {}).get("currency", ""),
                    payment_method="paypal",
                    payment_id=sale.get("id", ""),
                    metadata={
                        "payer_email": sale.get("payer", {}).get("payer_info", {}).get("email", "")
                    }
                )
                return 200, {"success": True}
                
            return 200, {"success": True, "message": "Event not processed"}
        except Exception as e:
            logger.error(f"PayPal webhook processing failed: {str(e)}")
            return 400, {"success": False, "error": str(e)}

    async def _record_transaction(self, amount: float, currency: str, payment_method: str, payment_id: str, metadata: Dict[str, Any]) -> None:
        """Record transaction in revenue tracking database."""
        try:
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source,
                    metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {int(amount * 100)},
                    '{currency}',
                    '{payment_method}',
                    '{json.dumps(metadata)}',
                    NOW(),
                    NOW()
                )
            """)
        except Exception as e:
            logger.error(f"Failed to record transaction: {str(e)}")
            raise

    async def create_subscription(self, customer_id: str, plan_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"plan": plan_id}],
                metadata=metadata
            )
            return {"success": True, "subscription_id": subscription.id}
        except Exception as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a subscription."""
        try:
            subscription = stripe.Subscription.delete(subscription_id)
            return {"success": True, "status": subscription.status}
        except Exception as e:
            logger.error(f"Subscription cancellation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def process_refund(self, payment_id: str, amount: float, reason: str) -> Dict[str, Any]:
        """Process a refund."""
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_id,
                amount=int(amount * 100),
                reason=reason
            )
            await self._record_transaction(
                amount=-amount,
                currency="usd",
                payment_method="stripe",
                payment_id=refund.id,
                metadata={"reason": reason}
            )
            return {"success": True, "refund_id": refund.id}
        except Exception as e:
            logger.error(f"Refund processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
