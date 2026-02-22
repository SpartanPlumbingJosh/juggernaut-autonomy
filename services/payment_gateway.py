import os
import stripe
import paddle
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum

class PaymentProvider(Enum):
    STRIPE = "stripe"
    PADDLE = "paddle"

class PaymentGateway:
    def __init__(self):
        self.stripe_api_key = os.getenv("STRIPE_API_KEY")
        self.paddle_vendor_id = os.getenv("PADDLE_VENDOR_ID")
        self.paddle_auth_code = os.getenv("PADDLE_AUTH_CODE")
        
        if self.stripe_api_key:
            stripe.api_key = self.stripe_api_key

    async def create_customer(
        self,
        email: str,
        name: str,
        payment_method: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create customer in payment provider."""
        if self.stripe_api_key:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                payment_method=payment_method,
                metadata=metadata or {}
            )
            return {
                "provider": PaymentProvider.STRIPE.value,
                "customer_id": customer.id,
                "payment_method": customer.invoice_settings.default_payment_method
            }
        elif self.paddle_vendor_id:
            # Paddle implementation would go here
            pass
        raise ValueError("No payment provider configured")

    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        quantity: int = 1,
        trial_days: int = 0,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create subscription for customer."""
        if self.stripe_api_key:
            sub = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id, "quantity": quantity}],
                trial_period_days=trial_days,
                metadata=metadata or {}
            )
            return {
                "provider": PaymentProvider.STRIPE.value,
                "subscription_id": sub.id,
                "status": sub.status,
                "current_period_end": sub.current_period_end
            }
        elif self.paddle_vendor_id:
            # Paddle implementation would go here
            pass
        raise ValueError("No payment provider configured")

    async def record_payment_event(self, event_data: Dict) -> Dict:
        """Record payment event in our system."""
        # Implementation would record in revenue_events table
        pass

    async def handle_webhook(self, payload: Dict, signature: str) -> Dict:
        """Process webhook from payment provider."""
        if self.stripe_api_key:
            try:
                event = stripe.Webhook.construct_event(
                    payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET")
                )
                return await self._process_stripe_event(event)
            except Exception as e:
                raise ValueError(f"Invalid webhook: {str(e)}")
        elif self.paddle_vendor_id:
            # Paddle webhook verification
            pass
        raise ValueError("No payment provider configured")

    async def _process_stripe_event(self, event: Dict) -> Dict:
        """Process Stripe webhook event."""
        event_type = event["type"]
        data = event["data"]["object"]
        
        if event_type == "invoice.paid":
            await self.record_payment_event({
                "event_type": "payment",
                "amount": data["amount_paid"],
                "currency": data["currency"],
                "invoice_id": data["id"],
                "customer_id": data["customer"],
                "metadata": data.get("metadata", {})
            })
        elif event_type == "invoice.payment_failed":
            # Handle failed payment
            pass
        
        return {"success": True, "event": event_type}
