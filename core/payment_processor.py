from __future__ import annotations
import os
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import stripe
import paddle

logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Core payment processing functionality supporting Stripe and Paddle."""
    
    def __init__(self):
        self.stripe_api_key = os.getenv("STRIPE_API_KEY")
        self.paddle_vendor_id = os.getenv("PADDLE_VENDOR_ID")
        self.paddle_auth_code = os.getenv("PADDLE_AUTH_CODE")
        
        if self.stripe_api_key:
            stripe.api_key = self.stripe_api_key
            stripe.api_version = "2023-08-16"
        
        if self.paddle_vendor_id and self.paddle_auth_code:
            paddle.set_vendor_id(self.paddle_vendor_id)
            paddle.set_api_key(self.paddle_auth_code)
    
    async def create_subscription(
        self,
        customer_email: str,
        plan_id: str,
        payment_method: str = "stripe",
        currency: str = "usd",
        tax_rates: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new subscription."""
        if payment_method == "stripe":
            return await self._create_stripe_subscription(
                customer_email, plan_id, currency, tax_rates, metadata
            )
        elif payment_method == "paddle":
            return await self._create_paddle_subscription(
                customer_email, plan_id, currency, metadata
            )
        else:
            raise ValueError(f"Unsupported payment method: {payment_method}")
    
    async def _create_stripe_subscription(
        self,
        customer_email: str,
        plan_id: str,
        currency: str,
        tax_rates: Optional[List[str]],
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create subscription via Stripe."""
        try:
            customer = stripe.Customer.create(email=customer_email)
            
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{"price": plan_id}],
                default_tax_rates=tax_rates,
                expand=["latest_invoice.payment_intent"],
                metadata=metadata or {}
            )
            
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "payment_intent": subscription.latest_invoice.payment_intent,
                "customer_id": customer.id
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription creation failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _create_paddle_subscription(
        self,
        customer_email: str,
        plan_id: str,
        currency: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create subscription via Paddle."""
        try:
            subscription = paddle.Subscription.create(
                plan_id=plan_id,
                customer_email=customer_email,
                currency=currency,
                passthrough=json.dumps(metadata or {})
            )
            
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.state,
                "checkout_url": subscription.checkout.url,
                "customer_id": subscription.customer_id
            }
        except paddle.PaddleException as e:
            logger.error(f"Paddle subscription creation failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def handle_webhook(
        self,
        payload: bytes,
        signature: Optional[str] = None,
        source: str = "stripe"
    ) -> Dict[str, Any]:
        """Process payment webhook events."""
        if source == "stripe":
            return await self._handle_stripe_webhook(payload, signature)
        elif source == "paddle":
            return await self._handle_paddle_webhook(payload)
        else:
            raise ValueError(f"Unsupported webhook source: {source}")
    
    async def _handle_stripe_webhook(
        self,
        payload: bytes,
        signature: Optional[str]
    ) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET")
            )
            
            event_type = event["type"]
            data = event["data"]["object"]
            
            if event_type == "invoice.payment_succeeded":
                return await self._process_payment_success(data)
            elif event_type == "invoice.payment_failed":
                return await self._process_payment_failure(data)
            elif event_type == "customer.subscription.deleted":
                return await self._process_subscription_cancellation(data)
            else:
                return {"success": True, "handled": False}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Stripe webhook signature verification failed: {str(e)}")
            return {"success": False, "error": "Invalid signature"}
        except Exception as e:
            logger.error(f"Stripe webhook processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _handle_paddle_webhook(self, payload: bytes) -> Dict[str, Any]:
        """Process Paddle webhook events."""
        try:
            event = json.loads(payload.decode("utf-8"))
            event_type = event["alert_name"]
            
            if event_type == "subscription_payment_succeeded":
                return await self._process_payment_success(event)
            elif event_type == "subscription_payment_failed":
                return await self._process_payment_failure(event)
            elif event_type == "subscription_cancelled":
                return await self._process_subscription_cancellation(event)
            else:
                return {"success": True, "handled": False}
        except Exception as e:
            logger.error(f"Paddle webhook processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _process_payment_success(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment event."""
        # TODO: Implement payment success handling
        return {"success": True, "handled": True}
    
    async def _process_payment_failure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment event."""
        # TODO: Implement payment failure handling
        return {"success": True, "handled": True}
    
    async def _process_subscription_cancellation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription cancellation."""
        # TODO: Implement cancellation handling
        return {"success": True, "handled": True}
