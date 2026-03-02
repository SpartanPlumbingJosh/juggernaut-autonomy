from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from .models import Subscription, SubscriptionPlan, SubscriptionStatus
import stripe
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class SubscriptionService:
    def __init__(self):
        self.plans = {
            "basic": SubscriptionPlan(
                id="basic",
                name="Basic Plan",
                price_cents=9900,
                interval="month",
                features={"storage": "10GB", "support": "email"}
            ),
            "pro": SubscriptionPlan(
                id="pro",
                name="Pro Plan",
                price_cents=19900,
                interval="month",
                features={"storage": "50GB", "support": "24/7"}
            )
        }

    async def create_subscription(self, user_id: str, plan_id: str, payment_token: str) -> Subscription:
        """Create a new subscription with Stripe payment"""
        plan = self.plans.get(plan_id)
        if not plan:
            raise ValueError("Invalid plan ID")

        # Create Stripe customer
        customer = stripe.Customer.create(
            source=payment_token,
            email=user_id,  # Using user_id as email for simplicity
            description=f"Customer for {user_id}"
        )

        # Create Stripe subscription
        stripe_sub = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": plan.id}],
            trial_end="now"  # Start immediately
        )

        # Create our subscription record
        subscription = Subscription(
            id=stripe_sub.id,
            user_id=user_id,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=datetime.fromtimestamp(stripe_sub.current_period_start),
            end_date=datetime.fromtimestamp(stripe_sub.current_period_end)
        )

        return subscription

    async def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel a subscription"""
        stripe.Subscription.delete(subscription_id)
        return True

    async def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """Retrieve subscription details"""
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        plan = self.plans.get(stripe_sub.plan.id)
        
        if not plan:
            return None

        return Subscription(
            id=stripe_sub.id,
            user_id=stripe_sub.customer,
            plan=plan,
            status=SubscriptionStatus(stripe_sub.status),
            start_date=datetime.fromtimestamp(stripe_sub.current_period_start),
            end_date=datetime.fromtimestamp(stripe_sub.current_period_end)
        )
