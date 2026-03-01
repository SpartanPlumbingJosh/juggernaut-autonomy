"""
Billing API - Handles Stripe integration and webhooks
"""
from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any
import json

from services.billing.service import BillingService

router = APIRouter()

@router.post("/webhook")
async def handle_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get('stripe-signature', '')
    
    result = await BillingService.handle_webhook(json.loads(payload), sig)
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('error'))
    return {"status": "success"}

@router.post("/customers")
async def create_customer(data: Dict[str, Any]):
    result = await BillingService.create_customer(
        data.get('email'),
        data.get('name')
    )
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('error'))
    return result

@router.post("/subscriptions")
async def create_subscription(data: Dict[str, Any]):
    result = await BillingService.create_subscription(
        data.get('customer_id'),
        data.get('price_id')
    )
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('error'))
    return result
