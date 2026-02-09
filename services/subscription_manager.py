"""
Subscription lifecycle management including:
- Trial periods
- Upgrades/downgrades
- Cancellation flows
- Renewal logic
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

from core.database import query_db
from services.payment_processor import PaymentProcessor

class SubscriptionAction(Enum):
    CREATE = "create"
    UPDATE = "update"
    CANCEL = "cancel"
    RENEW = "renew"

class SubscriptionManager:
    def __init__(self):
        self.payment_processor = PaymentProcessor()

    async def create_subscription(
        self,
        user_id: str,
        plan_id: str,
        payment_method: Dict[str, Any],
        trial_days: int = 0
    ) -> Dict[str, Any]:
        """Create new subscription for user."""
        # Get customer or create new
        customer_result = await query_db(
            f"""
            SELECT provider_id, provider
            FROM payment_customers
            WHERE user_id = '{user_id}'
            LIMIT 1
            """
        )
        customer = customer_result.get("rows", [{}])[0]

        if not customer.get("provider_id"):
            # Create new customer
            success, customer_id = await self.payment_processor.create_customer(
                user_id=user_id,
                email=user_email,
                name=user_name,
                payment_method=payment_method
            )
            if not success:
                return {"success": False, "error": "Failed to create customer"}

            # Store customer record
            await query_db(
                f"""
                INSERT INTO payment_customers (
                    id, user_id, provider_id, provider,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), '{user_id}', '{customer_id}',
                    'stripe', NOW(), NOW()
                )
                """
            )
        else:
            customer_id = customer["provider_id"]

        # Create subscription
        success, subscription_id = await self.payment_processor.create_subscription(
            customer_id=customer_id,
            plan_id=plan_id,
            trial_days=trial_days
        )
        if not success:
            return {"success": False, "error": "Failed to create subscription"}

        # Store subscription record
        await query_db(
            f"""
            INSERT INTO subscriptions (
                id, user_id, plan_id, provider_id,
                status, trial_ends_at, current_period_ends_at,
                created_at, updated_at
            ) VALUES (
                gen_random_uuid(), '{user_id}', '{plan_id}',
                '{subscription_id}', 
                '{"trialing" if trial_days > 0 else "active"}',
                {f"NOW() + INTERVAL '{trial_days} days'" if trial_days > 0 else "NULL"},
                NOW() + INTERVAL '1 month',
                NOW(), NOW()
            )
            """
        )

        return {"success": True, "subscription_id": subscription_id}

    async def cancel_subscription(
        self,
        subscription_id: str,
        cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """Cancel subscription immediately or at period end."""
        # Get subscription details
        result = await query_db(
            f"""
            SELECT provider_id, status
            FROM subscriptions
            WHERE id = '{subscription_id}'
            LIMIT 1
            """
        )
        subscription = result.get("rows", [{}])[0]

        if not subscription.get("provider_id"):
            return {"success": False, "error": "Subscription not found"}

        # Cancel with payment provider
        if cancel_at_period_end:
            # Schedule cancellation for period end
            await query_db(
                f"""
                UPDATE subscriptions
                SET cancel_at_period_end = TRUE,
                    updated_at = NOW()
                WHERE id = '{subscription_id}'
                """
            )
        else:
            # Cancel immediately
            await self.payment_processor._cancel_subscription(subscription["provider_id"])
        
        return {"success": True}

    async def process_subscription_renewals(self) -> Dict[str, Any]:
        """Process subscriptions due for renewal."""
        result = await query_db(
            """
            SELECT id, provider_id, plan_id, user_id
            FROM subscriptions
            WHERE status = 'active'
              AND current_period_ends_at <= NOW() + INTERVAL '7 days'
              AND cancel_at_period_end = FALSE
            LIMIT 100
            """
        )
        subscriptions = result.get("rows", [])

        renewed = 0
        for sub in subscriptions:
            try:
                # Extend subscription period
                await query_db(
                    f"""
                    UPDATE subscriptions
                    SET current_period_ends_at = current_period_ends_at + INTERVAL '1 month',
                        updated_at = NOW()
                    WHERE id = '{sub["id"]}'
                    """
                )
                renewed += 1
            except Exception as e:
                logger.error(f"Failed to renew subscription {sub['id']}: {str(e)}")

        return {"renewed": renewed, "total": len(subscriptions)}
