"""
Payment Processor - Handles payment integrations and billing logic.

Supports:
- Stripe
- PayPal
- Automated retries
- Webhook handling
- Subscription management
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import stripe
import paypalrestsdk

# Configure logging
logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self):
        self.stripe_api_key = os.getenv("STRIPE_API_KEY")
        self.paypal_client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.paypal_secret = os.getenv("PAYPAL_SECRET")
        
        stripe.api_key = self.stripe_api_key
        paypalrestsdk.configure({
            "mode": os.getenv("PAYPAL_MODE", "sandbox"),
            "client_id": self.paypal_client_id,
            "client_secret": self.paypal_secret
        })

    async def create_payment_intent(
        self,
        amount: float,
        currency: str = "usd",
        payment_method: str = "stripe",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Create a payment intent with retry logic."""
        metadata = metadata or {}
        attempts = 0
        max_attempts = 3
        
        while attempts < max_attempts:
            try:
                if payment_method == "stripe":
                    intent = stripe.PaymentIntent.create(
                        amount=int(amount * 100),  # Convert to cents
                        currency=currency,
                        metadata=metadata,
                        automatic_payment_methods={
                            "enabled": True,
                        },
                    )
                    return True, {
                        "client_secret": intent.client_secret,
                        "payment_id": intent.id,
                        "status": intent.status
                    }
                elif payment_method == "paypal":
                    payment = paypalrestsdk.Payment({
                        "intent": "sale",
                        "payer": {
                            "payment_method": "paypal"
                        },
                        "transactions": [{
                            "amount": {
                                "total": str(amount),
                                "currency": currency
                            }
                        }],
                        "redirect_urls": {
                            "return_url": os.getenv("PAYPAL_RETURN_URL"),
                            "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                        }
                    })
                    if payment.create():
                        return True, {
                            "payment_id": payment.id,
                            "approval_url": next(link.href for link in payment.links if link.rel == "approval_url"),
                            "status": payment.state
                        }
                    return False, {"error": "PayPal payment creation failed"}
                else:
                    return False, {"error": "Unsupported payment method"}
            except Exception as e:
                attempts += 1
                logger.error(f"Payment attempt {attempts} failed: {str(e)}")
                if attempts == max_attempts:
                    return False, {"error": str(e)}
                await asyncio.sleep(1)
        
        return False, {"error": "Max payment attempts reached"}

    async def handle_webhook(self, payload: Dict[str, Any], signature: Optional[str] = None) -> bool:
        """Process payment webhook events."""
        try:
            if signature:
                # Stripe webhook
                event = stripe.Webhook.construct_event(
                    payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET")
                )
                if event.type == "payment_intent.succeeded":
                    return await self._process_successful_payment(event.data.object)
            else:
                # PayPal webhook
                if payload.get("event_type") == "PAYMENT.SALE.COMPLETED":
                    return await self._process_successful_payment(payload)
            return False
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return False

    async def _process_successful_payment(self, payment_data: Dict[str, Any]) -> bool:
        """Record successful payment in revenue events."""
        try:
            amount = float(payment_data.get("amount") or payment_data.get("amount_total", 0)) / 100
            currency = payment_data.get("currency", "usd")
            payment_id = payment_data.get("id")
            
            # Record revenue event
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {int(amount * 100)},
                    '{currency}',
                    'payment_processor',
                    '{{"payment_id": "{payment_id}"}}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            return True
        except Exception as e:
            logger.error(f"Failed to record payment: {str(e)}")
            return False

    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        payment_method: str = "stripe"
    ) -> Tuple[bool, Dict[str, Any]]:
        """Create a subscription with retry logic."""
        attempts = 0
        max_attempts = 3
        
        while attempts < max_attempts:
            try:
                if payment_method == "stripe":
                    subscription = stripe.Subscription.create(
                        customer=customer_id,
                        items=[{"plan": plan_id}],
                        expand=["latest_invoice.payment_intent"]
                    )
                    return True, {
                        "subscription_id": subscription.id,
                        "status": subscription.status,
                        "current_period_end": subscription.current_period_end
                    }
                elif payment_method == "paypal":
                    agreement = paypalrestsdk.BillingAgreement({
                        "name": "Subscription Agreement",
                        "description": "Recurring subscription",
                        "start_date": (datetime.utcnow() + timedelta(minutes=5)).isoformat(),
                        "plan": {
                            "id": plan_id
                        },
                        "payer": {
                            "payment_method": "paypal"
                        }
                    })
                    if agreement.create():
                        return True, {
                            "agreement_id": agreement.id,
                            "status": agreement.state,
                            "approval_url": next(link.href for link in agreement.links if link.rel == "approval_url")
                        }
                    return False, {"error": "PayPal subscription creation failed"}
                else:
                    return False, {"error": "Unsupported payment method"}
            except Exception as e:
                attempts += 1
                logger.error(f"Subscription attempt {attempts} failed: {str(e)}")
                if attempts == max_attempts:
                    return False, {"error": str(e)}
                await asyncio.sleep(1)
        
        return False, {"error": "Max subscription attempts reached"}

payment_processor = PaymentProcessor()
