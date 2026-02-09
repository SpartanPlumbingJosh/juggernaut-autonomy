"""
Payment Processor - Handles Stripe/PayPal integrations and webhooks.
"""

import os
import stripe
import json
from datetime import datetime
from typing import Dict, Any, Optional

from core.database import query_db
from core.logging import log_action

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

class PaymentProcessor:
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
        except Exception as e:
            log_action("payment.customer_creation_failed", str(e), level="error")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def create_subscription(
        customer_id: str, 
        price_id: str, 
        payment_method_id: str
    ) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            # Attach payment method
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )

            # Set as default payment method
            stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    "default_payment_method": payment_method_id
                }
            )

            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                expand=["latest_invoice.payment_intent"]
            )
            
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "latest_invoice": subscription.latest_invoice.id
            }
        except Exception as e:
            log_action("payment.subscription_creation_failed", str(e), level="error")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def handle_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
            
            event_type = event['type']
            data = event['data']['object']
            
            # Handle different event types
            if event_type == 'payment_intent.succeeded':
                await PaymentProcessor._handle_payment_success(data)
            elif event_type == 'payment_intent.payment_failed':
                await PaymentProcessor._handle_payment_failure(data)
            elif event_type == 'invoice.paid':
                await PaymentProcessor._handle_invoice_paid(data)
            elif event_type == 'invoice.payment_failed':
                await PaymentProcessor._handle_invoice_failure(data)
            elif event_type == 'customer.subscription.deleted':
                await PaymentProcessor._handle_subscription_canceled(data)
            
            return {"success": True}
        except Exception as e:
            log_action("payment.webhook_failed", str(e), level="error")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def _handle_payment_success(data: Dict[str, Any]) -> None:
        """Handle successful payment."""
        amount = data['amount_received'] / 100  # Convert to dollars
        customer_id = data['customer']
        
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(amount * 100)},
                '{data['currency']}',
                'stripe',
                '{json.dumps(data)}'::jsonb,
                NOW()
            )
            """
        )
        log_action("payment.success", f"Payment received: {amount}", level="info")

    @staticmethod
    async def _handle_payment_failure(data: Dict[str, Any]) -> None:
        """Handle failed payment."""
        customer_id = data['customer']
        error = data.get('last_payment_error', {}).get('message', 'unknown')
        
        log_action(
            "payment.failed", 
            f"Payment failed for customer {customer_id}: {error}",
            level="warning"
        )
        
        # Trigger dunning process
        await PaymentProcessor._trigger_dunning_process(customer_id, error)

    @staticmethod
    async def _trigger_dunning_process(customer_id: str, error: str) -> None:
        """Handle failed payments with retry logic."""
        # Implement retry logic and email notifications
        pass

    @staticmethod
    async def _handle_invoice_paid(data: Dict[str, Any]) -> None:
        """Handle successful subscription payment."""
        amount = data['amount_paid'] / 100
        customer_id = data['customer']
        subscription_id = data['subscription']
        
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(amount * 100)},
                '{data['currency']}',
                'stripe',
                '{json.dumps({
                    'subscription_id': subscription_id,
                    'invoice_id': data['id'],
                    'customer_id': customer_id
                })}'::jsonb,
                NOW()
            )
            """
        )
        log_action(
            "subscription.payment_success",
            f"Subscription payment received: {amount}",
            level="info"
        )

    @staticmethod
    async def _handle_invoice_failure(data: Dict[str, Any]) -> None:
        """Handle failed subscription payment."""
        customer_id = data['customer']
        subscription_id = data['subscription']
        error = data.get('last_payment_error', {}).get('message', 'unknown')
        
        log_action(
            "subscription.payment_failed",
            f"Subscription payment failed: {error}",
            level="warning"
        )
        
        # Update subscription status in DB
        await query_db(
            f"""
            UPDATE subscriptions
            SET status = 'past_due',
                last_payment_error = '{error}',
                updated_at = NOW()
            WHERE stripe_subscription_id = '{subscription_id}'
            """
        )
        
        # Trigger dunning process
        await PaymentProcessor._trigger_dunning_process(customer_id, error)

    @staticmethod
    async def _handle_subscription_canceled(data: Dict[str, Any]) -> None:
        """Handle subscription cancellation."""
        subscription_id = data['id']
        
        await query_db(
            f"""
            UPDATE subscriptions
            SET status = 'canceled',
                canceled_at = NOW(),
                updated_at = NOW()
            WHERE stripe_subscription_id = '{subscription_id}'
            """
        )
        log_action(
            "subscription.canceled",
            f"Subscription canceled: {subscription_id}",
            level="info"
        )
