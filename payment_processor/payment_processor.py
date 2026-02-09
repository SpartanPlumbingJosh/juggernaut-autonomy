"""
Payment Processor - Handles Stripe/PayPal integrations, subscriptions, invoicing, and revenue recognition.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import stripe
import paypalrestsdk

from core.database import query_db

# Configure logging
logger = logging.getLogger(__name__)

# Initialize payment gateways
stripe.api_key = "sk_test_..."  # Should be from environment variables
paypalrestsdk.configure({
    "mode": "sandbox",  # or "live"
    "client_id": "...",
    "client_secret": "..."
})

class PaymentProcessor:
    def __init__(self):
        self.retry_attempts = 3
        self.retry_delay = 5  # seconds

    async def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a customer in both Stripe and PayPal."""
        try:
            # Create Stripe customer
            stripe_customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )

            # Create PayPal customer
            paypal_customer = paypalrestsdk.Customer({
                "email": email,
                "name": name,
                "metadata": metadata or {}
            }).create()

            return {
                "stripe_customer_id": stripe_customer.id,
                "paypal_customer_id": paypal_customer.id,
                "success": True
            }
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_subscription(self, customer_id: str, plan_id: str, payment_gateway: str = "stripe") -> Dict[str, Any]:
        """Create a subscription for a customer."""
        try:
            if payment_gateway == "stripe":
                subscription = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{"plan": plan_id}]
                )
            else:
                subscription = paypalrestsdk.Subscription({
                    "plan_id": plan_id,
                    "subscriber": {
                        "customer_id": customer_id
                    }
                }).create()

            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "success": True
            }
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_invoice(self, customer_id: str, amount: float, currency: str = "usd", 
                          description: str = "", metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create an invoice for a customer."""
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                amount=int(amount * 100),  # Convert to cents
                currency=currency,
                description=description,
                metadata=metadata or {}
            )

            return {
                "invoice_id": invoice.id,
                "amount": invoice.amount_due / 100,
                "currency": invoice.currency,
                "status": invoice.status,
                "success": True
            }
        except Exception as e:
            logger.error(f"Failed to create invoice: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: Dict[str, Any], signature: str, gateway: str) -> Dict[str, Any]:
        """Handle payment gateway webhooks."""
        try:
            if gateway == "stripe":
                event = stripe.Webhook.construct_event(
                    payload, signature, stripe.webhook_secret
                )
            else:
                event = paypalrestsdk.WebhookEvent.verify(
                    payload, signature
                )

            # Process event
            event_type = event["type"]
            data = event["data"]

            # Handle different event types
            if event_type == "payment_succeeded":
                await self._process_payment(data)
            elif event_type == "subscription_created":
                await self._process_subscription(data)
            elif event_type == "invoice_payment_failed":
                await self._handle_failed_payment(data)

            return {"success": True}
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _process_payment(self, data: Dict[str, Any]) -> None:
        """Process successful payment."""
        try:
            # Record revenue event
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source,
                    metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {int(data["amount"] * 100)},
                    '{data["currency"]}',
                    'payment_processor',
                    '{json.dumps(data)}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
        except Exception as e:
            logger.error(f"Failed to process payment: {str(e)}")

    async def _process_subscription(self, data: Dict[str, Any]) -> None:
        """Process new subscription."""
        try:
            # Record subscription event
            await query_db(f"""
                INSERT INTO subscriptions (
                    id, customer_id, subscription_id, status,
                    plan_id, start_date, end_date, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{data["customer_id"]}',
                    '{data["subscription_id"]}',
                    '{data["status"]}',
                    '{data["plan_id"]}',
                    NOW(),
                    NOW() + INTERVAL '1 month',
                    NOW()
                )
            """)
        except Exception as e:
            logger.error(f"Failed to process subscription: {str(e)}")

    async def _handle_failed_payment(self, data: Dict[str, Any]) -> None:
        """Handle failed payment with retry logic."""
        attempt = 0
        while attempt < self.retry_attempts:
            try:
                # Attempt to retry payment
                if data["payment_method"] == "stripe":
                    payment_intent = stripe.PaymentIntent.retrieve(data["payment_intent_id"])
                    payment_intent.confirm()
                else:
                    payment = paypalrestsdk.Payment.find(data["payment_id"])
                    payment.execute()

                if payment_intent.status == "succeeded":
                    await self._process_payment(data)
                    return

                attempt += 1
                await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Payment retry failed: {str(e)}")
                attempt += 1
                await asyncio.sleep(self.retry_delay)

        # If all retries fail, mark payment as failed
        await query_db(f"""
            INSERT INTO payment_failures (
                id, customer_id, amount, currency,
                failure_reason, attempt_count, created_at
            ) VALUES (
                gen_random_uuid(),
                '{data["customer_id"]}',
                {data["amount"]},
                '{data["currency"]}',
                'Max retries exceeded',
                {attempt},
                NOW()
            )
        """)

    async def generate_usage_billing(self, customer_id: str, usage_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate usage-based billing."""
        try:
            # Calculate usage charges
            total_amount = sum(usage_data["usage"]) * usage_data["rate"]
            
            # Create invoice
            invoice = await self.create_invoice(
                customer_id=customer_id,
                amount=total_amount,
                description=f"Usage billing for {usage_data['period']}"
            )

            return invoice
        except Exception as e:
            logger.error(f"Failed to generate usage billing: {str(e)}")
            return {"success": False, "error": str(e)}

    async def recognize_revenue(self, invoice_id: str) -> Dict[str, Any]:
        """Recognize revenue for an invoice."""
        try:
            # Get invoice details
            invoice = stripe.Invoice.retrieve(invoice_id)
            
            # Record revenue recognition
            await query_db(f"""
                INSERT INTO revenue_recognition (
                    id, invoice_id, amount, currency,
                    recognition_date, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{invoice_id}',
                    {invoice.amount_due / 100},
                    '{invoice.currency}',
                    NOW(),
                    NOW()
                )
            """)

            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to recognize revenue: {str(e)}")
            return {"success": False, "error": str(e)}
