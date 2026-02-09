"""
Payment processing service with Stripe/PayPal integration, subscription management,
dunning workflows, and revenue recognition.
"""
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import stripe
import paypalrestsdk

from core.database import query_db
from core.config import settings

# Configure payment providers
stripe.api_key = settings.STRIPE_SECRET_KEY
paypalrestsdk.configure({
    "mode": settings.PAYPAL_MODE,
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_SECRET
})

logger = logging.getLogger(__name__)

class PaymentProvider(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    CANCELED = "canceled"
    TRIALING = "trialing"

class PaymentProcessor:
    def __init__(self):
        self.dunning_attempts = 3
        self.dunning_intervals = [1, 3, 7]  # Days between attempts

    async def create_customer(
        self,
        user_id: str,
        email: str,
        name: str,
        payment_method: Dict[str, Any],
        provider: PaymentProvider = PaymentProvider.STRIPE
    ) -> Tuple[bool, Optional[str]]:
        """Create customer in payment provider."""
        try:
            if provider == PaymentProvider.STRIPE:
                customer = stripe.Customer.create(
                    email=email,
                    name=name,
                    payment_method=payment_method["id"],
                    invoice_settings={
                        "default_payment_method": payment_method["id"]
                    },
                    metadata={"user_id": user_id}
                )
                return True, customer.id
            
            elif provider == PaymentProvider.PAYPAL:
                # PayPal implementation
                pass
            
            return False, None
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return False, None

    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        trial_days: int = 0,
        provider: PaymentProvider = PaymentProvider.STRIPE
    ) -> Tuple[bool, Optional[str]]:
        """Create subscription for customer."""
        try:
            if provider == PaymentProvider.STRIPE:
                subscription = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{"plan": plan_id}],
                    trial_period_days=trial_days,
                    payment_behavior="default_incomplete",
                    expand=["latest_invoice.payment_intent"]
                )
                return True, subscription.id
            
            return False, None
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return False, None

    async def handle_webhook_event(self, event: Dict[str, Any]) -> bool:
        """Process payment provider webhook events."""
        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})

        if event_type == "invoice.payment_failed":
            await self._handle_failed_payment(data)
        elif event_type == "invoice.payment_succeeded":
            await self._handle_successful_payment(data)
        elif event_type == "customer.subscription.deleted":
            await self._handle_subscription_canceled(data)
        
        return True

    async def _handle_failed_payment(self, invoice: Dict[str, Any]) -> None:
        """Process failed payment with dunning logic."""
        customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")
        attempt_count = invoice.get("attempt_count", 0)

        if attempt_count >= self.dunning_attempts:
            await self._cancel_subscription(subscription_id)
            return

        next_attempt_days = self.dunning_intervals[min(
            attempt_count, 
            len(self.dunning_intervals) - 1
        )]

        # Schedule next attempt
        await query_db(
            f"""
            INSERT INTO payment_retries (
                id, customer_id, subscription_id, 
                attempt_number, scheduled_at, status
            ) VALUES (
                gen_random_uuid(), '{customer_id}', '{subscription_id}',
                {attempt_count + 1}, 
                NOW() + INTERVAL '{next_attempt_days} days',
                'scheduled'
            )
            """
        )

    async def _handle_successful_payment(self, invoice: Dict[str, Any]) -> None:
        """Record successful payment and recognize revenue."""
        amount = invoice.get("amount_paid", 0) / 100  # Convert to dollars
        customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")

        # Record transaction
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, 
                currency, source, recorded_at,
                attribution
            ) VALUES (
                gen_random_uuid(), 'revenue', {int(amount * 100)},
                'usd', 'subscription', NOW(),
                '{{"subscription_id": "{subscription_id}", "customer_id": "{customer_id}"}}'::jsonb
            )
            """
        )

        # Update subscription status
        await query_db(
            f"""
            UPDATE subscriptions
            SET status = 'active',
                last_payment_at = NOW(),
                next_payment_at = NOW() + INTERVAL '1 month'
            WHERE provider_id = '{subscription_id}'
            """
        )

    async def _handle_subscription_canceled(self, subscription: Dict[str, Any]) -> None:
        """Handle subscription cancellation."""
        subscription_id = subscription.get("id")
        await query_db(
            f"""
            UPDATE subscriptions
            SET status = 'canceled',
                canceled_at = NOW()
            WHERE provider_id = '{subscription_id}'
            """
        )

    async def process_scheduled_payments(self) -> Dict[str, Any]:
        """Process all scheduled payments."""
        # Get payments due
        result = await query_db(
            """
            SELECT id, customer_id, subscription_id, attempt_number
            FROM payment_retries
            WHERE scheduled_at <= NOW()
              AND status = 'scheduled'
            LIMIT 100
            """
        )
        payments = result.get("rows", [])

        processed = 0
        for payment in payments:
            try:
                # Attempt payment
                invoice = stripe.Invoice.create(
                    customer=payment["customer_id"],
                    subscription=payment["subscription_id"],
                    auto_advance=True
                )
                
                # Update status
                await query_db(
                    f"""
                    UPDATE payment_retries
                    SET status = 'processed',
                        processed_at = NOW(),
                        invoice_id = '{invoice.id}'
                    WHERE id = '{payment["id"]}'
                    """
                )
                processed += 1
            except Exception as e:
                logger.error(f"Failed to process payment {payment['id']}: {str(e)}")
                await query_db(
                    f"""
                    UPDATE payment_retries
                    SET status = 'failed',
                        error = '{str(e)[:200]}'
                    WHERE id = '{payment["id"]}'
                    """
                )

        return {"processed": processed, "total": len(payments)}

    async def recognize_revenue(self) -> Dict[str, Any]:
        """Run revenue recognition for all unprocessed transactions."""
        result = await query_db(
            """
            SELECT id, amount_cents, recorded_at, attribution
            FROM revenue_events
            WHERE revenue_recognized = FALSE
              AND event_type = 'revenue'
            LIMIT 1000
            """
        )
        transactions = result.get("rows", [])

        recognized = 0
        for txn in transactions:
            try:
                # Calculate recognized revenue based on subscription period
                # This is a simplified example - real implementation would handle:
                # - Proration
                # - Deferred revenue
                # - ASC 606 compliance
                await query_db(
                    f"""
                    INSERT INTO recognized_revenue (
                        id, revenue_event_id, amount_cents,
                        recognition_date, period_start, period_end
                    ) VALUES (
                        gen_random_uuid(), '{txn["id"]}', {txn["amount_cents"]},
                        NOW(), 
                        DATE('{txn["recorded_at"]}'), 
                        DATE('{txn["recorded_at"]}') + INTERVAL '1 month'
                    )
                    """
                )

                # Mark as recognized
                await query_db(
                    f"""
                    UPDATE revenue_events
                    SET revenue_recognized = TRUE
                    WHERE id = '{txn["id"]}'
                    """
                )
                recognized += 1
            except Exception as e:
                logger.error(f"Failed to recognize revenue for {txn['id']}: {str(e)}")

        return {"recognized": recognized, "total": len(transactions)}
