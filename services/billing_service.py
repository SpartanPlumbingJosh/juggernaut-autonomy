"""
Autonomous Billing Service - Handles subscription management, invoicing, and payments.
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.database import query_db

class BillingService:
    def __init__(self):
        self.currency = "USD"  # Default currency

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method_id: str) -> Dict[str, Any]:
        """Create a new subscription for a customer."""
        try:
            # Get plan details
            plan = await self._get_plan(plan_id)
            if not plan:
                return {"success": False, "error": "Plan not found"}

            # Create subscription record
            subscription_id = await self._create_subscription_record(
                customer_id, 
                plan_id,
                plan["billing_interval"],
                plan["amount_cents"]
            )

            # Create initial payment
            payment = await self._create_payment(
                subscription_id,
                plan["amount_cents"],
                payment_method_id
            )

            return {
                "success": True,
                "subscription_id": subscription_id,
                "payment_id": payment["payment_id"],
                "next_billing_date": payment["next_billing_date"]
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve billing plan details."""
        sql = f"""
        SELECT id, name, amount_cents, billing_interval, currency
        FROM billing_plans
        WHERE id = '{plan_id}'
        """
        result = await query_db(sql)
        return result.get("rows", [{}])[0]

    async def _create_subscription_record(self, customer_id: str, plan_id: str, interval: str, amount_cents: int) -> str:
        """Create subscription record in database."""
        sql = f"""
        INSERT INTO subscriptions (
            id, customer_id, plan_id, status, 
            billing_interval, amount_cents, currency,
            created_at, next_billing_date
        ) VALUES (
            gen_random_uuid(),
            '{customer_id}',
            '{plan_id}',
            'active',
            '{interval}',
            {amount_cents},
            '{self.currency}',
            NOW(),
            NOW() + INTERVAL '1 {interval}'
        )
        RETURNING id
        """
        result = await query_db(sql)
        return result.get("rows", [{}])[0].get("id")

    async def _create_payment(self, subscription_id: str, amount_cents: int, payment_method_id: str) -> Dict[str, Any]:
        """Create payment record and update subscription billing date."""
        sql = f"""
        WITH payment AS (
            INSERT INTO payments (
                id, subscription_id, amount_cents, currency,
                status, payment_method_id, created_at
            ) VALUES (
                gen_random_uuid(),
                '{subscription_id}',
                {amount_cents},
                '{self.currency}',
                'pending',
                '{payment_method_id}',
                NOW()
            )
            RETURNING id
        ),
        updated_sub AS (
            UPDATE subscriptions
            SET next_billing_date = NOW() + INTERVAL '1 month'
            WHERE id = '{subscription_id}'
            RETURNING next_billing_date
        )
        SELECT 
            p.id as payment_id,
            u.next_billing_date
        FROM payment p, updated_sub u
        """
        result = await query_db(sql)
        return result.get("rows", [{}])[0]

    async def process_recurring_payments(self) -> Dict[str, Any]:
        """Process all due recurring payments."""
        try:
            # Get subscriptions with due payments
            sql = """
            SELECT id, customer_id, plan_id, amount_cents
            FROM subscriptions
            WHERE next_billing_date <= NOW()
              AND status = 'active'
            """
            result = await query_db(sql)
            subscriptions = result.get("rows", [])

            processed = 0
            failures = []

            for sub in subscriptions:
                try:
                    # Get default payment method
                    payment_method = await self._get_default_payment_method(sub["customer_id"])
                    if not payment_method:
                        failures.append({
                            "subscription_id": sub["id"],
                            "error": "No payment method found"
                        })
                        continue

                    # Create payment
                    payment = await self._create_payment(
                        sub["id"],
                        sub["amount_cents"],
                        payment_method["id"]
                    )

                    processed += 1
                except Exception as e:
                    failures.append({
                        "subscription_id": sub["id"],
                        "error": str(e)
                    })

            return {
                "success": True,
                "processed": processed,
                "failures": failures
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _get_default_payment_method(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve customer's default payment method."""
        sql = f"""
        SELECT id, type, details
        FROM payment_methods
        WHERE customer_id = '{customer_id}'
          AND is_default = TRUE
        LIMIT 1
        """
        result = await query_db(sql)
        return result.get("rows", [{}])[0]

    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel an active subscription."""
        try:
            sql = f"""
            UPDATE subscriptions
            SET status = 'canceled',
                canceled_at = NOW()
            WHERE id = '{subscription_id}'
            RETURNING id
            """
            result = await query_db(sql)
            if result.get("rows"):
                return {"success": True, "subscription_id": subscription_id}
            return {"success": False, "error": "Subscription not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
