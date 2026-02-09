from datetime import datetime, timedelta
from typing import Dict, Optional, List
from enum import Enum
import json
from core.payment_gateways import PaymentGatewayClient, PaymentGateway

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    UNPAID = "unpaid"

class SubscriptionManager:
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql
        self.payment_client = PaymentGatewayClient()

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new subscription"""
        try:
            # Get plan details
            plan = await self.get_plan(plan_id)
            if not plan:
                return {"success": False, "error": "Plan not found"}

            # Create payment method
            payment_result = await self.payment_client.create_payment_method(
                payment_method,
                PaymentGateway.STRIPE if payment_method.get("type") == "card" else PaymentGateway.PAYPAL
            )
            if not payment_result.get("success"):
                return payment_result

            # Create subscription
            subscription_data = {
                "customer_id": customer_id,
                "plan_id": plan_id,
                "status": SubscriptionStatus.TRIALING.value if plan.get("trial_days", 0) > 0 else SubscriptionStatus.ACTIVE.value,
                "current_period_start": datetime.utcnow(),
                "current_period_end": datetime.utcnow() + timedelta(days=plan["interval_days"]),
                "trial_end": datetime.utcnow() + timedelta(days=plan.get("trial_days", 0)) if plan.get("trial_days", 0) > 0 else None,
                "payment_method_id": payment_result["payment_method_id"],
                "metadata": {}
            }

            # Save to database
            await self.execute_sql(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status,
                    current_period_start, current_period_end,
                    trial_end, payment_method_id, metadata
                ) VALUES (
                    gen_random_uuid(),
                    '{subscription_data["customer_id"]}',
                    '{subscription_data["plan_id"]}',
                    '{subscription_data["status"]}',
                    '{subscription_data["current_period_start"].isoformat()}',
                    '{subscription_data["current_period_end"].isoformat()}',
                    {f"'{subscription_data['trial_end'].isoformat()}'" if subscription_data['trial_end'] else "NULL"},
                    '{subscription_data["payment_method_id"]}',
                    '{json.dumps(subscription_data["metadata"])}'::jsonb
                )
                """
            )

            return {"success": True, "subscription": subscription_data}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get subscription plan details"""
        try:
            result = await self.execute_sql(
                f"SELECT * FROM subscription_plans WHERE id = '{plan_id}' LIMIT 1"
            )
            return result.get("rows", [{}])[0]
        except Exception:
            return None

    async def process_payment(self, subscription_id: str) -> Dict[str, Any]:
        """Process subscription payment"""
        try:
            # Get subscription details
            subscription = await self.get_subscription(subscription_id)
            if not subscription:
                return {"success": False, "error": "Subscription not found"}

            # Get plan details
            plan = await self.get_plan(subscription["plan_id"])
            if not plan:
                return {"success": False, "error": "Plan not found"}

            # Process payment
            payment_result = await self.payment_client.create_payment(
                plan["amount"],
                plan["currency"],
                PaymentGateway.STRIPE if subscription["payment_method"]["type"] == "card" else PaymentGateway.PAYPAL,
                {"subscription_id": subscription_id}
            )

            if not payment_result.get("success"):
                # Handle payment failure
                await self.execute_sql(
                    f"""
                    UPDATE subscriptions
                    SET status = '{SubscriptionStatus.PAST_DUE.value}'
                    WHERE id = '{subscription_id}'
                    """
                )
                return payment_result

            # Update subscription
            await self.execute_sql(
                f"""
                UPDATE subscriptions
                SET status = '{SubscriptionStatus.ACTIVE.value}',
                    current_period_start = '{datetime.utcnow().isoformat()}',
                    current_period_end = '{(datetime.utcnow() + timedelta(days=plan["interval_days"])).isoformat()}'
                WHERE id = '{subscription_id}'
                """
            )

            return {"success": True, "payment": payment_result}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get subscription details"""
        try:
            result = await self.execute_sql(
                f"SELECT * FROM subscriptions WHERE id = '{subscription_id}' LIMIT 1"
            )
            return result.get("rows", [{}])[0]
        except Exception:
            return None

    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a subscription"""
        try:
            await self.execute_sql(
                f"""
                UPDATE subscriptions
                SET status = '{SubscriptionStatus.CANCELED.value}',
                    canceled_at = NOW()
                WHERE id = '{subscription_id}'
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: Dict[str, Any], gateway: PaymentGateway) -> Dict[str, Any]:
        """Process subscription-related webhook events"""
        try:
            result = await self.payment_client.handle_webhook(payload, gateway)
            if not result.get("success"):
                return result

            # Handle subscription updates based on payment status
            subscription_id = result["metadata"].get("subscription_id")
            if not subscription_id:
                return {"success": False, "error": "Missing subscription ID"}

            if result["status"] == PaymentStatus.SUCCEEDED.value:
                await self.process_payment(subscription_id)
            elif result["status"] == PaymentStatus.FAILED.value:
                await self.execute_sql(
                    f"""
                    UPDATE subscriptions
                    SET status = '{SubscriptionStatus.PAST_DUE.value}'
                    WHERE id = '{subscription_id}'
                    """
                )
            elif result["status"] == PaymentStatus.REFUNDED.value:
                await self.execute_sql(
                    f"""
                    UPDATE subscriptions
                    SET status = '{SubscriptionStatus.CANCELED.value}'
                    WHERE id = '{subscription_id}'
                    """
                )

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}
