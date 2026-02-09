"""
Payment Processor - Handle payment processing logic and integration with payment providers.
"""

import stripe
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import query_db

class PaymentProcessor:
    def __init__(self):
        self.stripe = stripe
        self.stripe.api_key = "sk_test_..."  # Load from config
        
    async def create_subscription(self, customer_id: str, plan_id: str, payment_method_id: str) -> Dict[str, Any]:
        """Create new subscription."""
        try:
            # Attach payment method to customer
            self.stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            # Set as default payment method
            self.stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    "default_payment_method": payment_method_id
                }
            )
            
            # Create subscription
            subscription = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id}],
                expand=["latest_invoice.payment_intent"]
            )
            
            # Record in database
            await query_db(f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status,
                    current_period_start, current_period_end,
                    created_at, updated_at
                ) VALUES (
                    '{subscription.id}',
                    '{customer_id}',
                    '{plan_id}',
                    '{subscription.status}',
                    '{datetime.fromtimestamp(subscription.current_period_start, tz=timezone.utc).isoformat()}',
                    '{datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc).isoformat()}',
                    NOW(),
                    NOW()
                )
            """)
            
            return subscription
        except Exception as e:
            raise Exception(f"Failed to create subscription: {str(e)}")
        
    async def handle_payment_success(self, data: Dict[str, Any]) -> None:
        """Handle successful payment."""
        payment_intent = data.get("object")
        amount = payment_intent.get("amount") / 100
        currency = payment_intent.get("currency")
        
        await query_db(f"""
            INSERT INTO payments (
                id, amount, currency, status,
                customer_id, payment_method_id,
                created_at
            ) VALUES (
                '{payment_intent.get("id")}',
                {amount},
                '{currency}',
                'succeeded',
                '{payment_intent.get("customer")}',
                '{payment_intent.get("payment_method")}',
                NOW()
            )
        """)
        
    async def handle_payment_failure(self, data: Dict[str, Any]) -> None:
        """Handle failed payment."""
        payment_intent = data.get("object")
        await query_db(f"""
            UPDATE payments
            SET status = 'failed',
                failure_message = '{payment_intent.get("last_payment_error", {}).get("message", "")}',
                updated_at = NOW()
            WHERE id = '{payment_intent.get("id")}'
        """)
        
    async def handle_invoice_payment(self, data: Dict[str, Any]) -> None:
        """Handle successful invoice payment."""
        invoice = data.get("object")
        await query_db(f"""
            INSERT INTO invoices (
                id, amount_due, amount_paid, currency,
                customer_id, subscription_id, status,
                created_at
            ) VALUES (
                '{invoice.get("id")}',
                {invoice.get("amount_due") / 100},
                {invoice.get("amount_paid") / 100},
                '{invoice.get("currency")}',
                '{invoice.get("customer")}',
                '{invoice.get("subscription")}',
                'paid',
                NOW()
            )
        """)
        
    async def handle_subscription_created(self, data: Dict[str, Any]) -> None:
        """Handle new subscription creation."""
        subscription = data.get("object")
        await query_db(f"""
            INSERT INTO subscriptions (
                id, customer_id, plan_id, status,
                current_period_start, current_period_end,
                created_at, updated_at
            ) VALUES (
                '{subscription.get("id")}',
                '{subscription.get("customer")}',
                '{subscription.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")}',
                '{subscription.get("status")}',
                '{datetime.fromtimestamp(subscription.get("current_period_start"), tz=timezone.utc).isoformat()}',
                '{datetime.fromtimestamp(subscription.get("current_period_end"), tz=timezone.utc).isoformat()}',
                NOW(),
                NOW()
            )
        """)
        
    async def handle_subscription_updated(self, data: Dict[str, Any]) -> None:
        """Handle subscription updates."""
        subscription = data.get("object")
        await query_db(f"""
            UPDATE subscriptions
            SET status = '{subscription.get("status")}',
                current_period_start = '{datetime.fromtimestamp(subscription.get("current_period_start"), tz=timezone.utc).isoformat()}',
                current_period_end = '{datetime.fromtimestamp(subscription.get("current_period_end"), tz=timezone.utc).isoformat()}',
                updated_at = NOW()
            WHERE id = '{subscription.get("id")}'
        """)
        
    async def handle_subscription_deleted(self, data: Dict[str, Any]) -> None:
        """Handle subscription cancellation."""
        subscription = data.get("object")
        await query_db(f"""
            UPDATE subscriptions
            SET status = 'canceled',
                updated_at = NOW()
            WHERE id = '{subscription.get("id")}'
        """)
        
    async def get_invoices(self, customer_id: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Get invoice history."""
        result = await query_db(f"""
            SELECT id, amount_due, amount_paid, currency,
                   status, created_at
            FROM invoices
            WHERE customer_id = '{customer_id}'
            ORDER BY created_at DESC
            LIMIT {limit}
            OFFSET {offset}
        """)
        return result.get("rows", [])
        
    async def record_usage(self, subscription_id: str, quantity: int, timestamp: str) -> None:
        """Record usage for metered billing."""
        await query_db(f"""
            INSERT INTO usage_records (
                subscription_id, quantity, timestamp,
                created_at
            ) VALUES (
                '{subscription_id}',
                {quantity},
                '{timestamp}',
                NOW()
            )
        """)
        
        # Report usage to Stripe
        self.stripe.SubscriptionItem.create_usage_record(
            subscription_id,
            quantity=quantity,
            timestamp=int(datetime.fromisoformat(timestamp).timestamp())
        )
