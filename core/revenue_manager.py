"""
Core Revenue Infrastructure - Handles subscriptions, payments, invoicing and revenue tracking.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable

import stripe
import paypalrestsdk

# Configure logging
logger = logging.getLogger(__name__)

class RevenueManager:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
        # Initialize payment gateways
        stripe.api_key = "sk_test_..."  # Should come from config
        paypalrestsdk.configure({
            "mode": "sandbox",  # "live" for production
            "client_id": "...",
            "client_secret": "..."
        })

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: str) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            # Create Stripe subscription
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id}],
                default_payment_method=payment_method,
                expand=["latest_invoice.payment_intent"]
            )
            
            # Record subscription in database
            await self.execute_sql(f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status, 
                    current_period_start, current_period_end,
                    created_at, updated_at
                ) VALUES (
                    '{subscription.id}', '{customer_id}', '{plan_id}', 'active',
                    to_timestamp({subscription.current_period_start}), 
                    to_timestamp({subscription.current_period_end}),
                    NOW(), NOW()
                )
            """)
            
            return {"success": True, "subscription": subscription}
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_payment_webhook(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment gateway webhook events."""
        try:
            event_type = event.get("type")
            
            if event_type == "invoice.payment_succeeded":
                await self._handle_payment_success(event)
            elif event_type == "invoice.payment_failed":
                await self._handle_payment_failure(event)
            elif event_type == "customer.subscription.deleted":
                await self._handle_subscription_cancellation(event)
                
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to process webhook: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _handle_payment_success(self, event: Dict[str, Any]) -> None:
        """Handle successful payment event."""
        invoice = event["data"]["object"]
        amount = invoice["amount_paid"] / 100  # Convert to dollars
        
        await self.execute_sql(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(), 'revenue', {int(amount * 100)}, 'usd',
                'subscription', '{json.dumps(invoice)}', NOW()
            )
        """)
        
        # Update subscription status
        await self.execute_sql(f"""
            UPDATE subscriptions
            SET status = 'active',
                updated_at = NOW()
            WHERE id = '{invoice['subscription']}'
        """)

    async def _handle_payment_failure(self, event: Dict[str, Any]) -> None:
        """Handle failed payment event."""
        invoice = event["data"]["object"]
        
        # Update subscription status
        await self.execute_sql(f"""
            UPDATE subscriptions
            SET status = 'past_due',
                updated_at = NOW()
            WHERE id = '{invoice['subscription']}'
        """)
        
        # Trigger dunning process
        await self._start_dunning_process(invoice["customer"], invoice["id"])

    async def _handle_subscription_cancellation(self, event: Dict[str, Any]) -> None:
        """Handle subscription cancellation."""
        subscription = event["data"]["object"]
        
        await self.execute_sql(f"""
            UPDATE subscriptions
            SET status = 'canceled',
                updated_at = NOW()
            WHERE id = '{subscription.id}'
        """)

    async def _start_dunning_process(self, customer_id: str, invoice_id: str) -> None:
        """Handle failed payment recovery process."""
        try:
            # Retry payment
            invoice = stripe.Invoice.retrieve(invoice_id)
            invoice.pay()
            
            # If successful, update status
            await self.execute_sql(f"""
                UPDATE subscriptions
                SET status = 'active',
                    updated_at = NOW()
                WHERE id = '{invoice['subscription']}'
            """)
        except stripe.error.CardError as e:
            # If retry fails, mark as failed
            await self.execute_sql(f"""
                UPDATE subscriptions
                SET status = 'failed',
                    updated_at = NOW()
                WHERE id = '{invoice['subscription']}'
            """)
            
            # Notify customer
            await self._notify_payment_failure(customer_id, invoice_id)

    async def _notify_payment_failure(self, customer_id: str, invoice_id: str) -> None:
        """Notify customer of payment failure."""
        # Implement notification logic (email, SMS, etc)
        pass

    async def generate_invoice(self, subscription_id: str) -> Dict[str, Any]:
        """Generate and send invoice for subscription."""
        try:
            invoice = stripe.Invoice.create(
                customer=subscription_id,
                auto_advance=True
            )
            return {"success": True, "invoice": invoice}
        except Exception as e:
            logger.error(f"Failed to generate invoice: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_revenue_summary(self) -> Dict[str, Any]:
        """Get revenue summary across all sources."""
        try:
            result = await self.execute_sql("""
                SELECT 
                    SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as total_revenue_cents,
                    SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as total_cost_cents,
                    COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count
                FROM revenue_events
            """)
            return {"success": True, "data": result.get("rows", [{}])[0]}
        except Exception as e:
            logger.error(f"Failed to get revenue summary: {str(e)}")
            return {"success": False, "error": str(e)}
