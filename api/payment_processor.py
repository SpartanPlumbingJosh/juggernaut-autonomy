import os
import stripe
import json
from datetime import datetime
from typing import Dict, Any, Optional

from core.database import query_db, execute_db

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

class PaymentProcessor:
    """Handle payment processing and subscription management."""
    
    @staticmethod
    async def create_customer(email: str, name: str) -> Dict[str, Any]:
        """Create a new Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"created_at": datetime.utcnow().isoformat()}
            )
            return {"success": True, "customer_id": customer.id}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def create_subscription(customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def handle_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
        except ValueError as e:
            return {"success": False, "error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            return {"success": False, "error": "Invalid signature"}

        # Handle different event types
        event_type = event['type']
        data = event['data']
        
        if event_type == 'customer.subscription.created':
            await PaymentProcessor._handle_subscription_created(data)
        elif event_type == 'customer.subscription.updated':
            await PaymentProcessor._handle_subscription_updated(data)
        elif event_type == 'invoice.payment_succeeded':
            await PaymentProcessor._handle_payment_succeeded(data)
        elif event_type == 'invoice.payment_failed':
            await PaymentProcessor._handle_payment_failed(data)
        
        return {"success": True}
    
    @staticmethod
    async def _handle_subscription_created(data: Dict[str, Any]) -> None:
        """Handle new subscription creation."""
        subscription = data['object']
        await execute_db(
            f"""
            INSERT INTO subscriptions (
                id, customer_id, status, current_period_start, current_period_end,
                cancel_at_period_end, created_at, updated_at
            ) VALUES (
                '{subscription.id}', '{subscription.customer}', '{subscription.status}',
                '{datetime.fromtimestamp(subscription.current_period_start).isoformat()}',
                '{datetime.fromtimestamp(subscription.current_period_end).isoformat()}',
                {subscription.cancel_at_period_end},
                NOW(), NOW()
            )
            """
        )
    
    @staticmethod
    async def _handle_subscription_updated(data: Dict[str, Any]) -> None:
        """Handle subscription updates."""
        subscription = data['object']
        await execute_db(
            f"""
            UPDATE subscriptions SET
                status = '{subscription.status}',
                current_period_start = '{datetime.fromtimestamp(subscription.current_period_start).isoformat()}',
                current_period_end = '{datetime.fromtimestamp(subscription.current_period_end).isoformat()}',
                cancel_at_period_end = {subscription.cancel_at_period_end},
                updated_at = NOW()
            WHERE id = '{subscription.id}'
            """
        )
    
    @staticmethod
    async def _handle_payment_succeeded(data: Dict[str, Any]) -> None:
        """Handle successful payments."""
        invoice = data['object']
        await execute_db(
            f"""
            INSERT INTO payments (
                id, customer_id, amount, currency, status, invoice_url,
                created_at, updated_at
            ) VALUES (
                '{invoice.id}', '{invoice.customer}', {invoice.amount_paid},
                '{invoice.currency}', 'paid', '{invoice.hosted_invoice_url}',
                NOW(), NOW()
            )
            """
        )
    
    @staticmethod
    async def _handle_payment_failed(data: Dict[str, Any]) -> None:
        """Handle failed payments."""
        invoice = data['object']
        await execute_db(
            f"""
            INSERT INTO payments (
                id, customer_id, amount, currency, status, invoice_url,
                created_at, updated_at
            ) VALUES (
                '{invoice.id}', '{invoice.customer}', {invoice.amount_due},
                '{invoice.currency}', 'failed', '{invoice.hosted_invoice_url}',
                NOW(), NOW()
            )
            """
        )

__all__ = ["PaymentProcessor"]
