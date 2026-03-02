from datetime import datetime, timedelta
from typing import Dict, Optional
import stripe
import paddle

from billing.models import SubscriptionPlan, Subscription, UsageRecord
from core.database import query_db

class BillingService:
    def __init__(self, stripe_api_key: str, paddle_vendor_id: str):
        stripe.api_key = stripe_api_key
        self.paddle_vendor_id = paddle_vendor_id

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method_id: str) -> Subscription:
        """Create a new subscription."""
        # Check if plan exists
        plan = await query_db(
            f"SELECT * FROM subscription_plans WHERE id = '{plan_id}' LIMIT 1"
        )
        if not plan.get("rows"):
            raise ValueError("Plan not found")
        
        # Create subscription in Stripe
        stripe_sub = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": plan_id}],
            default_payment_method=payment_method_id,
            expand=["latest_invoice.payment_intent"]
        )
        
        # Save to database
        subscription = Subscription(
            id=stripe_sub.id,
            customer_id=customer_id,
            plan_id=plan_id,
            status=stripe_sub.status,
            current_period_start=datetime.fromtimestamp(stripe_sub.current_period_start),
            current_period_end=datetime.fromtimestamp(stripe_sub.current_period_end),
            cancel_at_period_end=stripe_sub.cancel_at_period_end,
            metadata=stripe_sub.metadata
        )
        
        await query_db(
            f"""
            INSERT INTO subscriptions (id, customer_id, plan_id, status, current_period_start, 
                current_period_end, cancel_at_period_end, metadata, created_at, updated_at)
            VALUES ('{subscription.id}', '{subscription.customer_id}', '{subscription.plan_id}', 
                '{subscription.status}', '{subscription.current_period_start.isoformat()}', 
                '{subscription.current_period_end.isoformat()}', {subscription.cancel_at_period_end}, 
                '{json.dumps(subscription.metadata)}', NOW(), NOW())
            """
        )
        
        return subscription

    async def record_usage(self, subscription_id: str, quantity: int) -> UsageRecord:
        """Record usage for metered billing."""
        # Get subscription
        sub = await query_db(
            f"SELECT * FROM subscriptions WHERE id = '{subscription_id}' LIMIT 1"
        )
        if not sub.get("rows"):
            raise ValueError("Subscription not found")
        
        # Create usage record
        usage = UsageRecord(
            id=str(uuid.uuid4()),
            subscription_id=subscription_id,
            timestamp=datetime.utcnow(),
            quantity=quantity,
            action="increment"
        )
        
        await query_db(
            f"""
            INSERT INTO usage_records (id, subscription_id, timestamp, quantity, action)
            VALUES ('{usage.id}', '{usage.subscription_id}', '{usage.timestamp.isoformat()}', 
                {usage.quantity}, '{usage.action}')
            """
        )
        
        # Report usage to Stripe
        stripe.SubscriptionItem.create_usage_record(
            sub["rows"][0]["stripe_subscription_item_id"],
            quantity=quantity,
            timestamp=int(datetime.utcnow().timestamp())
        )
        
        return usage

    async def cancel_subscription(self, subscription_id: str) -> Subscription:
        """Cancel a subscription."""
        # Cancel in Stripe
        stripe_sub = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )
        
        # Update database
        await query_db(
            f"""
            UPDATE subscriptions 
            SET status = 'canceled', updated_at = NOW()
            WHERE id = '{subscription_id}'
            """
        )
        
        return Subscription(
            id=stripe_sub.id,
            customer_id=stripe_sub.customer,
            plan_id=stripe_sub.plan.id,
            status=stripe_sub.status,
            current_period_start=datetime.fromtimestamp(stripe_sub.current_period_start),
            current_period_end=datetime.fromtimestamp(stripe_sub.current_period_end),
            cancel_at_period_end=stripe_sub.cancel_at_period_end,
            metadata=stripe_sub.metadata
        )

    async def get_invoices(self, customer_id: str, limit: int = 10) -> List[Dict]:
        """Retrieve customer invoices."""
        invoices = stripe.Invoice.list(
            customer=customer_id,
            limit=limit
        )
        return [dict(invoice) for invoice in invoices.data]
