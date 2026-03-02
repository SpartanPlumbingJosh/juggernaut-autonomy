import os
import json
import stripe
import paypalrestsdk
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

# Initialize payment gateways
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

class PaymentProcessor:
    """Autonomous payment processing system handling Stripe and PayPal integrations."""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=10)
        
    async def create_payment_intent(self, amount: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payment intent for immediate payment."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata,
                payment_method_types=['card']
            )
            return {"success": True, "client_secret": intent.client_secret}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def create_subscription(self, plan_id: str, customer_id: str, trial_days: int = 0) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"plan": plan_id}],
                trial_period_days=trial_days
            )
            return {"success": True, "subscription_id": subscription.id}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def handle_webhook(self, payload: str, sig_header: str, endpoint_secret: str) -> Dict[str, Any]:
        """Process incoming webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
            
            # Handle event types
            if event['type'] == 'payment_intent.succeeded':
                await self._handle_payment_success(event)
            elif event['type'] == 'charge.failed':
                await self._handle_payment_failure(event)
            elif event['type'] == 'invoice.payment_succeeded':
                await self._handle_invoice_payment(event)
            elif event['type'] == 'customer.subscription.deleted':
                await self._handle_subscription_cancellation(event)
                
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def _handle_payment_success(self, event: Dict[str, Any]) -> None:
        """Handle successful payment."""
        payment_intent = event['data']['object']
        # Log payment and trigger fulfillment
        
    async def _handle_payment_failure(self, event: Dict[str, Any]) -> None:
        """Handle failed payment attempt."""
        charge = event['data']['object']
        # Trigger dunning process
        
    async def _handle_invoice_payment(self, event: Dict[str, Any]) -> None:
        """Handle successful invoice payment."""
        invoice = event['data']['object']
        # Update subscription status
        
    async def _handle_subscription_cancellation(self, event: Dict[str, Any]) -> None:
        """Handle subscription cancellation."""
        subscription = event['data']['object']
        # Update customer status
        
    async def generate_invoice(self, customer_id: str) -> Dict[str, Any]:
        """Generate and send an invoice."""
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                auto_advance=True
            )
            return {"success": True, "invoice_id": invoice.id}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def calculate_usage_billing(self, customer_id: str, usage_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate usage-based billing."""
        try:
            # Create usage record
            stripe.SubscriptionItem.create_usage_record(
                customer_id,
                quantity=usage_data['quantity'],
                timestamp=int(datetime.now().timestamp())
            )
            return {"success": True}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def manage_dunning(self, customer_id: str) -> Dict[str, Any]:
        """Handle failed payment recovery."""
        try:
            # Retrieve customer payment methods
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type="card"
            )
            
            # Attempt payment with each method
            for method in payment_methods:
                try:
                    payment_intent = stripe.PaymentIntent.create(
                        amount=1000,  # Example amount
                        currency="usd",
                        customer=customer_id,
                        payment_method=method.id,
                        confirm=True
                    )
                    if payment_intent.status == 'succeeded':
                        return {"success": True}
                except stripe.error.StripeError:
                    continue
                    
            return {"success": False, "error": "All payment attempts failed"}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
