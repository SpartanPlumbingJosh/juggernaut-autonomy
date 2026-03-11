"""
Subscription Service - Manages recurring subscriptions.
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

class SubscriptionPlan(BaseModel):
    id: str
    name: str
    price_cents: int
    interval: str  # "month", "year"
    features: Dict[str, bool]

class CreateSubscriptionRequest(BaseModel):
    customer_id: str
    plan_id: str
    payment_method_id: Optional[str] = None
    trial_days: int = 0

@app.post("/subscriptions")
async def create_subscription(request: CreateSubscriptionRequest):
    # In a real implementation, this would create a Stripe subscription
    # For now we'll mock the response
    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=30)  # Default to monthly
    
    return JSONResponse({
        "id": "sub_mock123",
        "status": "active",
        "current_period_start": start_date.isoformat(),
        "current_period_end": end_date.isoformat(),
        "plan_id": request.plan_id
    })

@app.get("/subscriptions/{subscription_id}")
async def get_subscription(subscription_id: str):
    # Mock response
    return JSONResponse({
        "id": subscription_id,
        "status": "active",
        "plan_id": "pro_monthly"
    })
