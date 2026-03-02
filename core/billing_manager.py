"""
Billing Manager - Handles subscription management, payment processing, and automated billing.
Integrates with Stripe/Paddle and ensures 99.9% uptime through retries and fallback providers.
"""

import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import stripe
import paddle

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize payment providers
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paddle.api_key = os.getenv("PADDLE_SECRET_KEY")

class BillingManager:
    """Core billing operations and subscription management."""
    
    def __init__(self):
        self.provider_order = ["stripe", "paddle"]  # Primary and fallback providers
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        
    async def create_subscription(self, customer_data: Dict[str, Any], plan_id: str) -> Dict[str, Any]:
        """
        Create a new subscription with retry logic across providers.
        """
        last_error = None
        
        for provider in self.provider_order:
            for attempt in range(self.max_retries):
                try:
                    if provider == "stripe":
                        return await self._create_stripe_subscription(customer_data, plan_id)
                    elif provider == "paddle":
                        return await self._create_paddle_subscription(customer_data, plan_id)
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"Attempt {attempt + 1} failed with {provider}: {last_error}")
                    time.sleep(self.retry_delay)
        
        raise Exception(f"All providers failed: {last_error}")
    
    async def _create_stripe_subscription(self, customer_data: Dict[str, Any], plan_id: str) -> Dict[str, Any]:
        """Create subscription using Stripe"""
        customer = stripe.Customer.create(
            email=customer_data["email"],
            name=customer_data.get("name"),
            payment_method=customer_data["payment_method_id"],
            invoice_settings={
                "default_payment_method": customer_data["payment_method_id"]
            }
        )
        
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": plan_id}],
            expand=["latest_invoice.payment_intent"]
        )
        
        return {
            "subscription_id": subscription.id,
            "status": subscription.status,
            "payment_intent": subscription.latest_invoice.payment_intent
        }
    
    async def _create_paddle_subscription(self, customer_data: Dict[str, Any], plan_id: str) -> Dict[str, Any]:
        """Create subscription using Paddle"""
        subscription = paddle.Subscription.create(
            plan_id=plan_id,
            customer_email=customer_data["email"],
            payment_method=customer_data["payment_method_id"]
        )
        
        return {
            "subscription_id": subscription.id,
            "status": subscription.status
        }
    
    async def process_payment(self, amount: float, currency: str, payment_method: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process payment with retry logic across providers.
        """
        last_error = None
        
        for provider in self.provider_order:
            for attempt in range(self.max_retries):
                try:
                    if provider == "stripe":
                        return await self._process_stripe_payment(amount, currency, payment_method)
                    elif provider == "paddle":
                        return await self._process_paddle_payment(amount, currency, payment_method)
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"Attempt {attempt + 1} failed with {provider}: {last_error}")
                    time.sleep(self.retry_delay)
        
        raise Exception(f"All providers failed: {last_error}")
    
    async def _process_stripe_payment(self, amount: float, currency: str, payment_method: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment using Stripe"""
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency=currency.lower(),
            payment_method=payment_method["id"],
            confirm=True,
            capture_method="automatic"
        )
        
        return {
            "payment_id": intent.id,
            "status": intent.status,
            "amount": intent.amount / 100,
            "currency": intent.currency
        }
    
    async def _process_paddle_payment(self, amount: float, currency: str, payment_method: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment using Paddle"""
        payment = paddle.Payment.create(
            amount=amount,
            currency=currency,
            payment_method=payment_method["id"]
        )
        
        return {
            "payment_id": payment.id,
            "status": payment.status,
            "amount": payment.amount,
            "currency": payment.currency
        }
    
    async def handle_webhook(self, provider: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process webhook events from payment providers.
        """
        if provider == "stripe":
            return await self._handle_stripe_webhook(payload)
        elif provider == "paddle":
            return await self._handle_paddle_webhook(payload)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def _handle_stripe_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Stripe webhook events"""
        event = stripe.Event.construct_from(payload, stripe.api_key)
        
        if event.type == "payment_intent.succeeded":
            return await self._handle_payment_success(event.data.object)
        elif event.type == "invoice.payment_failed":
            return await self._handle_payment_failure(event.data.object)
        elif event.type == "customer.subscription.deleted":
            return await self._handle_subscription_cancelled(event.data.object)
        
        return {"status": "unhandled_event"}
    
    async def _handle_paddle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Paddle webhook events"""
        event = paddle.Event.construct_from(payload, paddle.api_key)
        
        if event.event_type == "subscription_created":
            return await self._handle_subscription_created(event.data)
        elif event.event_type == "subscription_cancelled":
            return await self._handle_subscription_cancelled(event.data)
        elif event.event_type == "payment_succeeded":
            return await self._handle_payment_success(event.data)
        
        return {"status": "unhandled_event"}
    
    async def _handle_payment_success(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment"""
        # TODO: Implement payment success handling
        return {"status": "success"}
    
    async def _handle_payment_failure(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment"""
        # TODO: Implement payment failure handling
        return {"status": "failure"}
    
    async def _handle_subscription_created(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle new subscription"""
        # TODO: Implement subscription creation handling
        return {"status": "created"}
    
    async def _handle_subscription_cancelled(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription cancellation"""
        # TODO: Implement subscription cancellation handling
        return {"status": "cancelled"}
