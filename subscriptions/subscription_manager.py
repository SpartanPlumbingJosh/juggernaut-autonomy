"""
Subscription Manager - Handles subscription plans, user subscriptions, and recurring payments.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional

class SubscriptionManager:
    def __init__(self, payment_processor):
        self.payment_processor = payment_processor

    async def create_subscription_plan(self, plan_id: str, name: str, amount: float, 
                                     currency: str, interval: str, interval_count: int) -> Dict[str, Any]:
        """Create a new subscription plan."""
        try:
            # Create plan in Stripe
            stripe.Plan.create(
                id=plan_id,
                amount=int(amount * 100),
                currency=currency,
                interval=interval,
                interval_count=interval_count,
                product={"name": name}
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def subscribe_user(self, user_id: str, plan_id: str, payment_method: str) -> Dict[str, Any]:
        """Subscribe a user to a plan."""
        try:
            # Create subscription in Stripe
            subscription = stripe.Subscription.create(
                customer=user_id,
                items=[{"plan": plan_id}],
                default_payment_method=payment_method
            )
            
            # Record in database
            sql = f"""
            INSERT INTO subscriptions (
                id, user_id, plan_id, status, 
                start_date, end_date, created_at
            ) VALUES (
                gen_random_uuid(),
                '{user_id}',
                '{plan_id}',
                'active',
                NOW(),
                NOW() + INTERVAL '1 {subscription.plan.interval}',
                NOW()
            )
            """
            await query_db(sql)
            return {"success": True, "subscription_id": subscription.id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def process_recurring_payments(self) -> Dict[str, Any]:
        """Process all due recurring payments."""
        try:
            # Get subscriptions due for renewal
            sql = """
            SELECT id, user_id, plan_id 
            FROM subscriptions 
            WHERE end_date <= NOW() 
              AND status = 'active'
            """
            result = await query_db(sql)
            subscriptions = result.get("rows", [])
            
            processed = 0
            for sub in subscriptions:
                # Process payment
                payment_result = await self.payment_processor.create_payment_intent(
                    amount=100.0,  # Example amount
                    currency="usd",
                    metadata={
                        "subscription_id": sub["id"],
                        "user_id": sub["user_id"]
                    }
                )
                
                if payment_result["success"]:
                    # Update subscription
                    update_sql = f"""
                    UPDATE subscriptions
                    SET end_date = NOW() + INTERVAL '1 month',
                        updated_at = NOW()
                    WHERE id = '{sub["id"]}'
                    """
                    await query_db(update_sql)
                    processed += 1
            
            return {"success": True, "processed": processed}
        except Exception as e:
            return {"success": False, "error": str(e)}
