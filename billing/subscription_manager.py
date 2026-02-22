from typing import Dict, Optional
from datetime import datetime, timedelta
from core.database import query_db, execute_db
from billing.payment_gateway import PaymentGateway

class SubscriptionManager:
    def __init__(self, payment_gateway: PaymentGateway):
        self.payment_gateway = payment_gateway
        
    def create_subscription(self, customer_id: str, plan_id: str, payment_method_id: str) -> Dict:
        """Create a new subscription"""
        # Create Stripe subscription
        subscription = self.payment_gateway.create_subscription(
            customer_id=customer_id,
            price_id=plan_id
        )
        
        # Store in database
        execute_db(
            f"""
            INSERT INTO subscriptions (
                id, customer_id, plan_id, status,
                start_date, end_date, stripe_id,
                created_at, updated_at
            ) VALUES (
                gen_random_uuid(),
                '{customer_id}',
                '{plan_id}',
                'active',
                NOW(),
                NOW() + INTERVAL '1 month',
                '{subscription['id']}',
                NOW(),
                NOW()
            )
            """
        )
        
        return {
            "success": True,
            "subscription_id": subscription['id']
        }
        
    def cancel_subscription(self, subscription_id: str) -> Dict:
        """Cancel a subscription"""
        # Get Stripe subscription ID
        res = query_db(
            f"""
            SELECT stripe_id
            FROM subscriptions
            WHERE id = '{subscription_id}'
            """
        )
        stripe_id = res.get("rows", [{}])[0].get("stripe_id")
        
        if not stripe_id:
            return {"success": False, "error": "Subscription not found"}
            
        # Cancel in Stripe
        stripe.Subscription.delete(stripe_id)
        
        # Update database
        execute_db(
            f"""
            UPDATE subscriptions
            SET status = 'canceled',
                end_date = NOW(),
                updated_at = NOW()
            WHERE id = '{subscription_id}'
            """
        )
        
        return {"success": True}
        
    def renew_subscription(self, subscription_id: str) -> Dict:
        """Renew a subscription"""
        # Get subscription details
        res = query_db(
            f"""
            SELECT stripe_id, plan_id
            FROM subscriptions
            WHERE id = '{subscription_id}'
            """
        )
        row = res.get("rows", [{}])[0]
        stripe_id = row.get("stripe_id")
        plan_id = row.get("plan_id")
        
        if not stripe_id:
            return {"success": False, "error": "Subscription not found"}
            
        # Renew in Stripe
        subscription = stripe.Subscription.modify(
            stripe_id,
            cancel_at_period_end=False,
            items=[{"price": plan_id}]
        )
        
        # Update database
        execute_db(
            f"""
            UPDATE subscriptions
            SET status = 'active',
                end_date = NOW() + INTERVAL '1 month',
                updated_at = NOW()
            WHERE id = '{subscription_id}'
            """
        )
        
        return {"success": True}
        
    def get_subscription(self, subscription_id: str) -> Optional[Dict]:
        """Get subscription details"""
        res = query_db(
            f"""
            SELECT *
            FROM subscriptions
            WHERE id = '{subscription_id}'
            """
        )
        return res.get("rows", [{}])[0]
