"""
Subscription Management System - Handles recurring payments, plans, and customer subscriptions.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import stripe
from dataclasses import dataclass
from enum import Enum

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"

@dataclass
class SubscriptionPlan:
    id: str
    name: str
    amount: int  # In cents
    currency: str
    interval: str  # day, week, month, year
    interval_count: int
    metadata: Dict[str, str]

@dataclass
class Subscription:
    id: str
    customer_id: str
    plan: SubscriptionPlan
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    metadata: Dict[str, str]

class SubscriptionManager:
    def __init__(self):
        self.stripe = stripe

    async def create_plan(self, plan: SubscriptionPlan) -> SubscriptionPlan:
        """Create a new subscription plan."""
        try:
            stripe_plan = self.stripe.Plan.create(
                id=plan.id,
                amount=plan.amount,
                currency=plan.currency,
                interval=plan.interval,
                interval_count=plan.interval_count,
                product={
                    "name": plan.name
                },
                metadata=plan.metadata
            )
            return SubscriptionPlan(
                id=stripe_plan.id,
                name=stripe_plan.product.name,
                amount=stripe_plan.amount,
                currency=stripe_plan.currency,
                interval=stripe_plan.interval,
                interval_count=stripe_plan.interval_count,
                metadata=stripe_plan.metadata
            )
        except Exception as e:
            raise ValueError(f"Failed to create plan: {str(e)}")

    async def create_subscription(self, customer_id: str, plan_id: str, metadata: Dict[str, str]) -> Subscription:
        """Create a new subscription."""
        try:
            stripe_sub = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{"plan": plan_id}],
                metadata=metadata
            )
            return self._convert_stripe_subscription(stripe_sub)
        except Exception as e:
            raise ValueError(f"Failed to create subscription: {str(e)}")

    async def cancel_subscription(self, subscription_id: str) -> Subscription:
        """Cancel a subscription."""
        try:
            stripe_sub = self.stripe.Subscription.delete(subscription_id)
            return self._convert_stripe_subscription(stripe_sub)
        except Exception as e:
            raise ValueError(f"Failed to cancel subscription: {str(e)}")

    def _convert_stripe_subscription(self, stripe_sub) -> Subscription:
        """Convert Stripe subscription to our model."""
        return Subscription(
            id=stripe_sub.id,
            customer_id=stripe_sub.customer,
            plan=self._convert_stripe_plan(stripe_sub.plan),
            status=SubscriptionStatus(stripe_sub.status),
            current_period_start=datetime.fromtimestamp(stripe_sub.current_period_start),
            current_period_end=datetime.fromtimestamp(stripe_sub.current_period_end),
            cancel_at_period_end=stripe_sub.cancel_at_period_end,
            metadata=stripe_sub.metadata
        )

    def _convert_stripe_plan(self, stripe_plan) -> SubscriptionPlan:
        """Convert Stripe plan to our model."""
        return SubscriptionPlan(
            id=stripe_plan.id,
            name=stripe_plan.product.name,
            amount=stripe_plan.amount,
            currency=stripe_plan.currency,
            interval=stripe_plan.interval,
            interval_count=stripe_plan.interval_count,
            metadata=stripe_plan.metadata
        )
