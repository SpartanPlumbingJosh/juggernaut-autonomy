from typing import Optional, Dict, List
from datetime import datetime, timedelta
import logging
from .models import (
    Subscription,
    SubscriptionPlan,
    Invoice,
    Payment,
    Customer,
    SubscriptionStatus,
    PaymentMethod
)
from .stripe_client import StripeClient
from core.database import query_db

logger = logging.getLogger(__name__)

class BillingService:
    def __init__(self, stripe_api_key: str):
        self.stripe = StripeClient(stripe_api_key)

    async def create_customer(self, email: str, name: str, payment_method: PaymentMethod) -> Customer:
        """Create a new billing customer"""
        try:
            stripe_customer = self.stripe.create_customer(email, name)
            return Customer(
                id=stripe_customer.id,
                email=email,
                name=name,
                payment_method=payment_method,
                created_at=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            raise

    async def create_subscription(self, customer_id: str, plan_id: str, trial_days: int = 0) -> Subscription:
        """Create a new subscription"""
        try:
            # Get plan details from database
            plan = await self._get_plan(plan_id)
            if not plan:
                raise ValueError("Plan not found")

            stripe_sub = self.stripe.create_subscription(
                customer_id,
                plan_id,
                trial_days
            )

            return Subscription(
                id=stripe_sub.id,
                customer_id=customer_id,
                plan_id=plan_id,
                status=SubscriptionStatus(stripe_sub.status),
                current_period_start=datetime.fromtimestamp(stripe_sub.current_period_start),
                current_period_end=datetime.fromtimestamp(stripe_sub.current_period_end),
                cancel_at_period_end=stripe_sub.cancel_at_period_end,
                payment_method=PaymentMethod.STRIPE
            )
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            raise

    async def cancel_subscription(self, subscription_id: str) -> Subscription:
        """Cancel a subscription"""
        try:
            stripe_sub = self.stripe.cancel_subscription(subscription_id)
            return Subscription(
                id=stripe_sub.id,
                customer_id=stripe_sub.customer,
                plan_id=stripe_sub.items.data[0].price.id,
                status=SubscriptionStatus(stripe_sub.status),
                current_period_start=datetime.fromtimestamp(stripe_sub.current_period_start),
                current_period_end=datetime.fromtimestamp(stripe_sub.current_period_end),
                cancel_at_period_end=stripe_sub.cancel_at_period_end,
                payment_method=PaymentMethod.STRIPE
            )
        except Exception as e:
            logger.error(f"Failed to cancel subscription: {str(e)}")
            raise

    async def generate_invoice(self, customer_id: str, amount_cents: int, currency: str = "usd") -> Invoice:
        """Generate an invoice for a customer"""
        try:
            stripe_invoice = self.stripe.create_invoice(customer_id, amount_cents, currency)
            return Invoice(
                id=stripe_invoice.id,
                customer_id=customer_id,
                amount_cents=stripe_invoice.amount_due,
                currency=currency,
                status=stripe_invoice.status,
                due_date=datetime.fromtimestamp(stripe_invoice.due_date),
                payment_method=PaymentMethod.STRIPE
            )
        except Exception as e:
            logger.error(f"Failed to generate invoice: {str(e)}")
            raise

    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict:
        """Handle Stripe webhook events"""
        try:
            return self.stripe.handle_webhook(payload, sig_header, webhook_secret)
        except Exception as e:
            logger.error(f"Webhook handling failed: {str(e)}")
            raise

    async def _get_plan(self, plan_id: str) -> Optional[SubscriptionPlan]:
        """Get subscription plan details from database"""
        try:
            res = await query_db(f"SELECT * FROM subscription_plans WHERE id = '{plan_id}'")
            if res.get("rows"):
                row = res["rows"][0]
                return SubscriptionPlan(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    price_cents=row["price_cents"],
                    currency=row["currency"],
                    billing_interval=row["billing_interval"],
                    features=row["features"]
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get plan: {str(e)}")
            raise
