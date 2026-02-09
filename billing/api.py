from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
from datetime import datetime
from .models import Subscription, Invoice
from .service import BillingService

router = APIRouter(prefix="/billing", tags=["billing"])

def get_billing_service() -> BillingService:
    # Initialize with your Stripe API key
    return BillingService(stripe_api_key="your_stripe_secret_key")

@router.post("/subscriptions")
async def create_subscription(
    customer_id: str,
    plan_id: str,
    trial_period_days: Optional[int] = None,
    billing_service: BillingService = Depends(get_billing_service)
):
    subscription = billing_service.create_subscription(
        customer_id=customer_id,
        plan_id=plan_id,
        trial_period_days=trial_period_days
    )
    if not subscription:
        raise HTTPException(status_code=400, detail="Failed to create subscription")
    return subscription

@router.get("/subscriptions/{subscription_id}")
async def get_subscription(
    subscription_id: str,
    billing_service: BillingService = Depends(get_billing_service)
):
    subscription = billing_service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription

@router.post("/webhook")
async def handle_webhook(
    payload: str,
    stripe_signature: str = Header(None),
    billing_service: BillingService = Depends(get_billing_service)
):
    success = billing_service.process_webhook(
        payload=payload,
        sig_header=stripe_signature,
        webhook_secret="your_webhook_secret"
    )
    if not success:
        raise HTTPException(status_code=400, detail="Webhook processing failed")
    return {"status": "success"}

@router.post("/invoices")
async def create_invoice(
    customer_id: str,
    amount_cents: int,
    currency: str,
    billing_service: BillingService = Depends(get_billing_service)
):
    invoice = billing_service.create_invoice(
        customer_id=customer_id,
        amount_cents=amount_cents,
        currency=currency
    )
    if not invoice:
        raise HTTPException(status_code=400, detail="Failed to create invoice")
    return invoice
