"""
Payment API Routes
"""
from fastapi import APIRouter, Request, HTTPException
from api.payment_processor import PaymentProcessor
from typing import Optional, Dict

router = APIRouter()

@router.post("/create-checkout")
async def create_checkout(
    product_id: str,
    quantity: int = 1,
    customer_email: Optional[str] = None,
    metadata: Optional[Dict] = None
):
    """Create checkout session"""
    return await PaymentProcessor.create_checkout_session(
        product_id=product_id,
        quantity=quantity,
        customer_email=customer_email,
        metadata=metadata
    )

@router.post("/create-subscription")
async def create_subscription(
    customer_id: str,
    price_id: str,
    metadata: Optional[Dict] = None
):
    """Create subscription"""
    return await PaymentProcessor.create_subscription(
        customer_id=customer_id,
        price_id=price_id,
        metadata=metadata
    )

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    return await PaymentProcessor.handle_webhook(request)

@router.get("/success")
async def payment_success(session_id: str):
    """Handle successful payment redirect"""
    # Verify payment and show success page
    session = stripe.checkout.Session.retrieve(session_id)
    if session.payment_status == 'paid':
        return {"status": "success"}
    return {"status": "pending"}

@router.get("/cancel")
async def payment_cancel():
    """Handle cancelled payment"""
    return {"status": "cancelled"}
