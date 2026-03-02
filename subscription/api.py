from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from .models import Subscription, SubscriptionPlan
from .service import SubscriptionService

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
service = SubscriptionService()

@router.get("/plans")
async def get_plans():
    """Get available subscription plans"""
    return list(service.plans.values())

@router.post("/subscribe")
async def create_subscription(plan_id: str, payment_token: str, token: str = Depends(oauth2_scheme)):
    """Create new subscription"""
    try:
        subscription = await service.create_subscription(token, plan_id, payment_token)
        return {"status": "success", "subscription_id": subscription.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/subscriptions/{subscription_id}")
async def get_subscription(subscription_id: str, token: str = Depends(oauth2_scheme)):
    """Get subscription details"""
    subscription = await service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription

@router.post("/subscriptions/{subscription_id}/cancel")
async def cancel_subscription(subscription_id: str, token: str = Depends(oauth2_scheme)):
    """Cancel subscription"""
    success = await service.cancel_subscription(subscription_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to cancel subscription")
    return {"status": "success"}
