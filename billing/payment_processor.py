import os
import stripe
import json
from datetime import datetime
from typing import Dict, Any, Optional
from core.database import query_db, execute_sql

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
        except Exception as e:
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
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def handle_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
            
            # Handle different event types
            if event["type"] == "invoice.payment_succeeded":
                await PaymentProcessor._handle_payment_success(event)
            elif event["type"] == "customer.subscription.updated":
                await PaymentProcessor._handle_subscription_update(event)
            elif event["type"] == "charge.refunded":
                await PaymentProcessor._handle_refund(event)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def _handle_payment_success(event: Dict[str, Any]) -> None:
        """Record successful payment in revenue database."""
        invoice = event["data"]["object"]
        amount = invoice["amount_paid"]
        customer_id = invoice["customer"]
        subscription_id = invoice["subscription"]
        
        await execute_sql(f"""
            INSERT INTO revenue_events (
                id, experiment_id, event_type, amount_cents,
                currency, source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                NULL,
                'revenue',
                {amount},
                '{invoice["currency"]}',
                'stripe',
                '{json.dumps({
                    "invoice_id": invoice["id"],
                    "customer_id": customer_id,
                    "subscription_id": subscription_id
                })}'::jsonb,
                NOW()
            )
        """)
    
    @staticmethod
    async def _handle_subscription_update(event: Dict[str, Any]) -> None:
        """Update subscription status in database."""
        subscription = event["data"]["object"]
        status = subscription["status"]
        customer_id = subscription["customer"]
        
        await execute_sql(f"""
            UPDATE subscriptions
            SET status = '{status}',
                updated_at = NOW()
            WHERE customer_id = '{customer_id}'
        """)
    
    @staticmethod
    async def _handle_refund(event: Dict[str, Any]) -> None:
        """Record refund in revenue database."""
        charge = event["data"]["object"]
        amount = charge["amount_refunded"]
        
        await execute_sql(f"""
            INSERT INTO revenue_events (
                id, experiment_id, event_type, amount_cents,
                currency, source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                NULL,
                'refund',
                {-amount},
                '{charge["currency"]}',
                'stripe',
                '{json.dumps({
                    "charge_id": charge["id"],
                    "reason": charge["refunds"]["data"][0].get("reason", "")
                })}'::jsonb,
                NOW()
            )
        """)
