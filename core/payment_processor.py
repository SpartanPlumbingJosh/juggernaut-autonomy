"""
Autonomous payment processing with Stripe/PayPal webhooks.
Handles payment events, logs transactions, and manages customer lifecycle.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logger = logging.getLogger(__name__)

# Maximum retries for payment processing operations
MAX_RETRIES = 3
RETRY_WAIT = 1  # seconds

class PaymentProcessor:
    def __init__(self, execute_sql: callable, stripe_api_key: str):
        """Initialize payment processor with DB access and Stripe config."""
        self.execute_sql = execute_sql
        stripe.api_key = stripe_api_key
        self.webhook_secret = None  # Set from config

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def handle_stripe_webhook(self, payload: str, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook event with verification and error handling."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
        except ValueError as e:
            logger.error(f"Invalid Stripe payload: {str(e)}")
            return {"status": "error", "message": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Stripe signature verification failed: {str(e)}")
            return {"status": "error", "message": "Invalid signature"}

        # Process supported event types
        event_type = event["type"]
        logger.info(f"Processing Stripe event: {event_type}")

        handlers = {
            "payment_intent.succeeded": self._handle_successful_payment,
            "invoice.paid": self._handle_invoice_payment,
            "customer.subscription.deleted": self._handle_subscription_canceled,
            "charge.refunded": self._handle_refund,
        }

        handler = handlers.get(event_type)
        if not handler:
            logger.info(f"Skipping unhandled event: {event_type}")
            return {"status": "skipped", "event_type": event_type}

        try:
            await handler(event["data"]["object"])
            return {"status": "success", "event_type": event_type}
        except Exception as e:
            logger.error(f"Failed to process {event_type}: {str(e)}", exc_info=True)
            # Will be retried by decorator
            raise

    async def _handle_successful_payment(self, payment_intent: Dict[str, Any]) -> None:
        """Log successful one-time payments."""
        amount = payment_intent["amount"] / 100  # Convert to dollars
        customer_id = payment_intent["customer"]
        currency = payment_intent["currency"].upper()
        
        sql = """
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                customer_id, source, recorded_at, metadata
            ) VALUES (
                gen_random_uuid(), 'revenue', %s, %s, 
                %s, 'stripe', NOW(), %s::jsonb
            )
        """
        metadata = {
            "payment_intent_id": payment_intent["id"],
            "payment_method": payment_intent.get("payment_method_type", "unknown"),
            "billing_details": payment_intent.get("billing_details", {}),
        }

        await self.execute_sql(sql, (
            int(amount * 100),  # Store as cents
            currency,
            customer_id,
            json.dumps(metadata),
        ))

        # Activate product access
        await self._activate_product_access(
            customer_id,
            payment_intent["metadata"].get("product_id"),
            payment_intent["metadata"].get("plan")
        )

    async def _handle_invoice_payment(self, invoice: Dict[str, Any]) -> None:
        """Handle recurring subscription payments."""
        subscription = invoice["subscription"]
        customer_id = invoice["customer"]
        amount = invoice["amount_paid"] / 100
        
        sql = """
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                customer_id, subscription_id, source, 
                recorded_at, metadata
            ) VALUES (
                gen_random_uuid(), 'revenue', %s, %s, 
                %s, %s, 'stripe', NOW(), %s::jsonb
            )
        """
        metadata = {
            "invoice_id": invoice["id"],
            "billing_reason": invoice.get("billing_reason"),
            "subscription_items": invoice.get("lines", {}).get("data", []),
        }

        await self.execute_sql(sql, (
            int(amount * 100),
            invoice["currency"].upper(),
            customer_id,
            subscription,
            json.dumps(metadata),
        ))

        # Update subscription status
        await self._update_subscription_status(subscription, "active")

    async def _handle_subscription_canceled(self, subscription: Dict[str, Any]) -> None:
        """Handle subscription cancellations."""
        await self._update_subscription_status(subscription["id"], "canceled")
        
        # Schedule retention actions if possible
        expires_at = subscription.get("current_period_end")
        if expires_at:
            await self._schedule_retention_email(
                subscription["customer"],
                datetime.fromtimestamp(expires_at, timezone.utc)
            )

    async def _handle_refund(self, charge: Dict[str, Any]) -> None:
        """Log refund events as negative revenue."""
        amount = charge["amount_refunded"] / 100 * -1  # Negative amount
        
        await self.execute_sql(
            """
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                customer_id, source, recorded_at, metadata
            ) VALUES (
                gen_random_uuid(), 'refund', %s, %s, 
                %s, 'stripe', NOW(), %s::jsonb
            )
            """,
            (
                int(amount * 100),
                charge["currency"].upper(),
                charge["customer"],
                json.dumps({"charge_id": charge["id"]}),
            )
        )

    async def _update_subscription_status(self, sub_id: str, status: str) -> None:
        """Update subscription status in database."""
        await self.execute_sql(
            """
            UPDATE subscriptions
            SET status = %s, 
                updated_at = NOW()
            WHERE stripe_id = %s
            """,
            (status, sub_id)
        )

    async def _activate_product_access(self, customer_id: str, product_id: Optional[str], plan: Optional[str]) -> None:
        """Grant product access to customer."""
        # Implementation depends on your product/service delivery system
        pass

    async def _schedule_retention_email(self, customer_id: str, expiry_date: datetime) -> None:
        """Schedule retention emails before subscription expires."""
        # Integration with email service would go here
        pass


def create_payment_processor(execute_sql: callable, config: Dict[str, Any]) -> PaymentProcessor:
    """Factory method to create configured payment processor."""
    processor = PaymentProcessor(execute_sql, config["stripe_api_key"])
    processor.webhook_secret = config["stripe_webhook_secret"]
    return processor
