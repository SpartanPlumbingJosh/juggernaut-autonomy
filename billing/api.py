from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Optional

from billing.models import (
    SubscriptionPlan,
    Subscription,
    Invoice,
    PaymentMethod,
    Customer
)
from billing.service import BillingService

router = APIRouter()

def get_billing_service() -> BillingService:
    return BillingService(stripe_api_key="your_stripe_secret_key")

@router.post("/customers", response_model=Customer)
async def create_customer(email: str, name: Optional[str] = None, 
                         billing_service: BillingService = Depends(get_billing_service)):
    return await billing_service.create_customer(email, name)

@router.post("/subscriptions", response_model=Subscription)
async def create_subscription(customer_id: str, plan_id: str, payment_method_id: str,
                             billing_service: BillingService = Depends(get_billing_service)):
    return await billing_service.create_subscription(customer_id, plan_id, payment_method_id)

@router.post("/subscriptions/{subscription_id}/cancel", response_model=Subscription)
async def cancel_subscription(subscription_id: str,
                             billing_service: BillingService = Depends(get_billing_service)):
    return await billing_service.cancel_subscription(subscription_id)

@router.post("/subscriptions/{subscription_id}/change_plan", response_model=Subscription)
async def change_subscription_plan(subscription_id: str, new_plan_id: str,
                                  billing_service: BillingService = Depends(get_billing_service)):
    return await billing_service.update_subscription_plan(subscription_id, new_plan_id)

@router.post("/webhooks/stripe")
async def handle_stripe_webhook(request: Request,
                               billing_service: BillingService = Depends(get_billing_service)):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    return await billing_service.handle_webhook_event(payload, sig_header, "your_webhook_secret")
