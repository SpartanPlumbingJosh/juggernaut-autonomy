from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict
from auth.auth_service import AuthService

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/users", response_model=List[Dict])
async def get_users(auth: AuthService = Depends()):
    # Implement proper admin check
    return list(auth.users_db.values())

@router.get("/subscriptions", response_model=List[Dict])
async def get_subscriptions(subscription_service: SubscriptionService = Depends()):
    return list(subscription_service.subscriptions_db.values())

@router.get("/metrics", response_model=Dict)
async def get_metrics():
    # Implement actual metrics collection
    return {
        "active_users": 0,
        "active_subscriptions": 0,
        "monthly_revenue": 0
    }
