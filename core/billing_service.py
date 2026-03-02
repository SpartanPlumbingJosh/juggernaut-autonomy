"""
Automated billing and subscription management service.
Integrates with payment processors and manages recurring billing cycles.
"""

import datetime
import json
import logging
from typing import Any, Dict, List, Optional

import stripe  # type: ignore
import paddle  # type: ignore

from core.database import query_db
from core.monitoring import AlertManager

logger = logging.getLogger(__name__)

class BillingService:
    def __init__(self, config: Dict[str, Any]):
        self.stripe_api_key = config.get("stripe_api_key")
        self.paddle_vendor_id = config.get("paddle_vendor_id")
        self.paddle_api_key = config.get("paddle_api_key")
        self.currency = config.get("currency", "usd")
        self.alert_manager = AlertManager(config)
        
        if self.stripe_api_key:
            stripe.api_key = self.stripe_api_key
        if self.paddle_vendor_id and self.paddle_api_key:
            paddle.set_vendor_id(self.paddle_vendor_id)
            paddle.set_api_key(self.paddle_api_key)

    async def process_recurring_billing(self) -> Dict[str, Any]:
        """Process all recurring subscriptions for current billing cycle."""
        try:
            # Get all active subscriptions due for billing
            subscriptions = await self._get_due_subscriptions()
            results = []
            
            for sub in subscriptions:
                try:
                    result = await self._process_subscription(sub)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to process subscription {sub['id']}: {str(e)}")
                    self.alert_manager.trigger_alert(
                        "billing_failed",
                        f"Subscription {sub['id']} processing failed",
                        {"subscription_id": sub["id"], "error": str(e)}
                    )
                    
            return {"success": True, "processed": len(results), "results": results}
            
        except Exception as e:
            logger.error(f"Failed billing cycle processing: {str(e)}")
            self.alert_manager.trigger_alert(
                "billing_cycle_failed",
                "Recurring billing cycle failed",
                {"error": str(e)}
            )
            return {"success": False, "error": str(e)}

    async def _get_due_subscriptions(self) -> List[Dict[str, Any]]:
        """Get subscriptions with upcoming or past due billing dates."""
        sql = """
        SELECT id, customer_id, plan_id, billing_cycle, next_billing_date, 
               payment_method, processor, metadata
        FROM subscriptions 
        WHERE status = 'active' 
          AND next_billing_date <= NOW()
        """
        result = await query_db(sql)
        return result.get("rows", [])

    async def _process_subscription(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment for a single subscription."""
        processor = subscription["processor"]
        amount = subscription["metadata"].get("amount")
        
        if processor == "stripe":
            return await self._process_stripe_payment(subscription)
        elif processor == "paddle":
            return await self._process_paddle_payment(subscription)
        else:
            raise ValueError(f"Unsupported payment processor: {processor}")

    async def _process_stripe_payment(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment via Stripe."""
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=subscription["metadata"]["amount"],
                currency=self.currency,
                customer=subscription["customer_id"],
                payment_method=subscription["payment_method"],
                confirm=True,
                metadata={
                    "subscription_id": subscription["id"],
                    "plan_id": subscription["plan_id"]
                }
            )
                        
            # Record successful payment
            await self._record_payment(
                subscription,
                payment_intent.id,
                payment_intent.amount,
                "completed"
            )
            
            return {"success": True, "subscription_id": subscription["id"]}
            
        except stripe.error.StripeError as e:
            await self._handle_payment_failure(subscription, str(e))
            raise

    async def _process_paddle_payment(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment via Paddle."""
        try:
            response = paddle.Subscription.update(
                subscription_id=subscription["customer_id"],  # Paddle sub ID 
                passthrough=subscription["id"],  # Our sub ID
                items=[{
                    "price_id": subscription["plan_id"],
                    "quantity": 1,
                }]
            )
            
            # Record successful payment
            await self._record_payment(
                subscription,
                response["order_id"],
                response["total"],
                "completed"
            )
            
            return {"success": True, "subscription_id": subscription["id"]}
            
        except paddle.PaddleException as e:
            await self._handle_payment_failure(subscription, str(e))
            raise

    async def _record_payment(self, subscription: Dict[str, Any], 
                            transaction_id: str, amount: int, status: str) -> None:
        """Record payment in database."""
        sql = f"""
        INSERT INTO payments (
            id, subscription_id, transaction_id, amount_cents,
            currency, processor, status, created_at
        ) VALUES (
            gen_random_uuid(), '{subscription["id"]}', '{transaction_id}',
            {amount}, '{self.currency}', '{subscription["processor"]}', 
            '{status}', NOW()
        )
        """
        await query_db(sql)
        
        # Update subscription billing dates
        next_billing_date = calculate_next_billing_date(
            subscription["billing_cycle"]
        )
        update_sql = f"""
        UPDATE subscriptions
        SET last_billing_date = NOW(),
            next_billing_date = '{next_billing_date.isoformat()}'
        WHERE id = '{subscription["id"]}'
        """
        await query_db(update_sql)

    async def _handle_payment_failure(self, subscription: Dict[str, Any], error: str) -> None:
        """Handle payment failures and update subscription status."""
        sql = f"""
        INSERT INTO payments (
            id, subscription_id, transaction_id, amount_cents,
            currency, processor, status, created_at, error
        ) VALUES (
            gen_random_uuid(), '{subscription["id"]}', NULL,
            {subscription["metadata"]["amount"]}, '{self.currency}', 
            '{subscription["processor"]}', 'failed', NOW(),
            '{error}'
        )
        """
        await query_db(sql)

        # After 3 failures, pause subscription
        failure_count = await self._get_failure_count(subscription["id"])
        if failure_count >= 3:
            pause_sql = f"""
            UPDATE subscriptions
            SET status = 'paused'
            WHERE id = '{subscription["id"]}'
            """
            await query_db(pause_sql)
            self.alert_manager.trigger_alert(
                "subscription_paused",
                f"Subscription {subscription['id']} paused due to recurring failures",
                {"subscription_id": subscription["id"], "failures": failure_count}
            )

    async def _get_failure_count(self, subscription_id: str) -> int:
        """Get recent payment failure count for subscription."""
        sql = f"""
        SELECT COUNT(*) as failures
        FROM payments
        WHERE subscription_id = '{subscription_id}'
          AND status = 'failed'
          AND created_at >= NOW() - INTERVAL '30 days'
        """
        result = await query_db(sql)
        return result.get("rows", [{}])[0].get("failures", 0)

def calculate_next_billing_date(billing_cycle: str) -> datetime.datetime:
    """Calculate next billing date based on cycle."""
    today = datetime.datetime.now()
    if billing_cycle == "monthly":
        return today + datetime.timedelta(days=30)
    elif billing_cycle == "quarterly":
        return today + datetime.timedelta(days=90)
    elif billing_cycle == "yearly": 
        return today + datetime.timedelta(days=365)
    else:
        raise ValueError(f"Unknown billing cycle: {billing_cycle}")
