"""
Payment Processor - Handles payment integrations and automated fulfillment.

Supports:
- Stripe
- PayPal
- Automated delivery/service provisioning
- Error handling and retries
"""

import os
import time
import json
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from core.database import query_db

# Initialize payment gateways
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

class PaymentProcessor:
    """Handles payment processing and fulfillment."""
    
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        
    async def process_payment(self, payment_method: str, amount: float, currency: str, 
                            metadata: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Process payment through selected gateway."""
        try:
            if payment_method == "stripe":
                return await self._process_stripe_payment(amount, currency, metadata)
            elif payment_method == "paypal":
                return await self._process_paypal_payment(amount, currency, metadata)
            else:
                raise ValueError(f"Unsupported payment method: {payment_method}")
        except Exception as e:
            return False, str(e)
            
    async def _process_stripe_payment(self, amount: float, currency: str, 
                                    metadata: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Process payment through Stripe."""
        try:
            # Convert amount to cents
            amount_cents = int(amount * 100)
            
            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata,
                capture_method="automatic"
            )
            
            # Confirm payment
            confirmed_intent = stripe.PaymentIntent.confirm(intent["id"])
            
            if confirmed_intent["status"] == "succeeded":
                await self._fulfill_order(metadata)
                return True, confirmed_intent["id"]
            else:
                return False, "Payment not succeeded"
                
        except stripe.error.StripeError as e:
            return False, str(e)
            
    async def _process_paypal_payment(self, amount: float, currency: str, 
                                    metadata: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Process payment through PayPal."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount:.2f}",
                        "currency": currency
                    },
                    "description": metadata.get("description", "Service Payment")
                }],
                "redirect_urls": {
                    "return_url": metadata.get("return_url", ""),
                    "cancel_url": metadata.get("cancel_url", "")
                }
            })
            
            if payment.create():
                # Execute payment
                payment.execute({"payer_id": payment.payer.payer_info.payer_id})
                
                if payment.state == "approved":
                    await self._fulfill_order(metadata)
                    return True, payment.id
                else:
                    return False, "Payment not approved"
            else:
                return False, payment.error
            
        except Exception as e:
            return False, str(e)
            
    async def _fulfill_order(self, metadata: Dict[str, Any]) -> bool:
        """Handle order fulfillment with retries."""
        for attempt in range(self.max_retries):
            try:
                # Record transaction
                await query_db(f"""
                    INSERT INTO revenue_events (
                        id, event_type, amount_cents, currency, 
                        source, metadata, recorded_at, created_at
                    ) VALUES (
                        gen_random_uuid(),
                        'revenue',
                        {int(float(metadata["amount"]) * 100)},
                        '{metadata["currency"]}',
                        '{metadata["source"]}',
                        '{json.dumps(metadata)}'::jsonb,
                        NOW(),
                        NOW()
                    )
                """)
                
                # Trigger fulfillment logic
                # This would call your actual fulfillment system
                self._trigger_fulfillment(metadata)
                
                return True
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                raise e
                
    def _trigger_fulfillment(self, metadata: Dict[str, Any]):
        """Trigger fulfillment process."""
        # Implement your specific fulfillment logic here
        # This could be:
        # - Digital product delivery
        # - Service provisioning
        # - API call to external system
        pass
        
    async def handle_webhook(self, payload: Dict[str, Any], signature: str, source: str) -> bool:
        """Handle payment webhooks."""
        try:
            if source == "stripe":
                event = stripe.Webhook.construct_event(
                    payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET")
                )
                return await self._handle_stripe_webhook(event)
            elif source == "paypal":
                return await self._handle_paypal_webhook(payload)
            else:
                raise ValueError(f"Unsupported webhook source: {source}")
        except Exception as e:
            return False
            
    async def _handle_stripe_webhook(self, event: Any) -> bool:
        """Handle Stripe webhook events."""
        event_type = event["type"]
        
        if event_type == "payment_intent.succeeded":
            metadata = event["data"]["object"]["metadata"]
            await self._fulfill_order(metadata)
            return True
            
        return False
        
    async def _handle_paypal_webhook(self, payload: Dict[str, Any]) -> bool:
        """Handle PayPal webhook events."""
        event_type = payload.get("event_type", "")
        
        if event_type == "PAYMENT.SALE.COMPLETED":
            metadata = payload.get("resource", {}).get("metadata", {})
            await self._fulfill_order(metadata)
            return True
            
        return False
