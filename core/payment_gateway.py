"""
Payment Gateway Integration - Handles Stripe/PayPal transactions and webhooks.
"""
import os
import json
import stripe
from typing import Dict, Any, Optional
from datetime import datetime

class PaymentGateway:
    def __init__(self):
        self.stripe_api_key = os.getenv('STRIPE_API_KEY')
        stripe.api_key = self.stripe_api_key

    async def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a new customer in Stripe."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer": customer}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Create a subscription for a customer."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                metadata=metadata or {},
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            return {"success": True, "subscription": subscription}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            event_type = event['type']
            data = event['data']['object']
            
            if event_type == 'invoice.paid':
                return await self._handle_payment_success(data)
            elif event_type == 'invoice.payment_failed':
                return await self._handle_payment_failure(data)
            elif event_type == 'customer.subscription.deleted':
                return await self._handle_subscription_cancelled(data)
            
            return {"success": True, "handled": False}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

    async def _handle_payment_success(self, invoice: Dict) -> Dict[str, Any]:
        """Handle successful payment event."""
        amount_paid = invoice['amount_paid']
        customer_id = invoice['customer']
        subscription_id = invoice['subscription']
        
        # Record revenue event
        revenue_event = {
            "event_type": "revenue",
            "amount_cents": amount_paid,
            "currency": invoice['currency'],
            "source": "stripe",
            "metadata": {
                "invoice_id": invoice['id'],
                "customer_id": customer_id,
                "subscription_id": subscription_id
            },
            "recorded_at": datetime.utcnow().isoformat()
        }
        
        return {
            "success": True,
            "handled": True,
            "action": "payment_success",
            "revenue_event": revenue_event
        }

    async def _handle_payment_failure(self, invoice: Dict) -> Dict[str, Any]:
        """Handle failed payment event."""
        return {
            "success": True,
            "handled": True,
            "action": "payment_failure",
            "customer_id": invoice['customer'],
            "subscription_id": invoice['subscription']
        }

    async def _handle_subscription_cancelled(self, subscription: Dict) -> Dict[str, Any]:
        """Handle subscription cancellation."""
        return {
            "success": True,
            "handled": True,
            "action": "subscription_cancelled",
            "customer_id": subscription['customer'],
            "subscription_id": subscription['id']
        }
