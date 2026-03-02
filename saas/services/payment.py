import stripe
from typing import Optional
from datetime import datetime
from fastapi import HTTPException
from saas.models.subscription import Subscription, SubscriptionCreate

class PaymentService:
    def __init__(self, stripe_api_key: str):
        stripe.api_key = stripe_api_key

    async def create_customer(self, email: str, payment_method_id: str) -> str:
        try:
            customer = stripe.Customer.create(
                email=email,
                payment_method=payment_method_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )
            return customer.id
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def create_subscription(self, customer_id: str, plan_id: str) -> Subscription:
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id}],
                expand=["latest_invoice.payment_intent"]
            )
            
            return Subscription(
                id=subscription.id,
                user_id=customer_id,
                plan=plan_id,
                status="active",
                start_date=datetime.fromtimestamp(subscription.current_period_start),
                end_date=datetime.fromtimestamp(subscription.current_period_end),
                renewal_date=datetime.fromtimestamp(subscription.current_period_end),
                payment_method_id=subscription.default_payment_method,
                price_cents=subscription.plan.amount
            )
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def cancel_subscription(self, subscription_id: str) -> bool:
        try:
            stripe.Subscription.delete(subscription_id)
            return True
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))
