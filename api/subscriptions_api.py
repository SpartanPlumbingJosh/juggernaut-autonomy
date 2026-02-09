"""
Subscription API endpoints for customer self-service and management.
"""

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.subscriptions.service import SubscriptionService
from core.database import query_db

router = APIRouter()
service = SubscriptionService()

class CreateSubscriptionRequest(BaseModel):
    customer_id: str
    plan_id: str
    payment_method: str
    quantity: int = 1
    trial_days: int = 0
    metadata: Optional[Dict[str, Any]] = None

@router.post("/subscriptions")
async def create_subscription(request: Request, data: CreateSubscriptionRequest):
    """Create new subscription."""
    try:
        result = await service.create_subscription(
            customer_id=data.customer_id,
            plan_id=data.plan_id,
            payment_method=data.payment_method,
            quantity=data.quantity,
            trial_days=data.trial_days,
            metadata=data.metadata
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return {"subscription_id": result["subscription"]}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/subscriptions/{subscription_id}")
async def get_subscription(subscription_id: str):
    """Get subscription details."""
    try:
        res = await query_db(
            f"""
            SELECT 
                s.id, s.customer_id, s.plan_id, s.status,
                s.current_period_start, s.current_period_end,
                s.created_at, s.updated_at, s.metadata,
                c.email, c.name,
                p.name as plan_name, p.amount as plan_amount
            FROM subscriptions s
            JOIN customers c ON s.customer_id = c.id
            JOIN plans p ON s.plan_id = p.id
            WHERE s.id = '{subscription_id}'
            """
        )
        
        if not res.get("rows"):
            raise HTTPException(status_code=404, detail="Subscription not found")
            
        return res["rows"][0]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/subscriptions/{subscription_id}/cancel")
async def cancel_subscription(subscription_id: str):
    """Cancel subscription at period end."""
    try:
        # Update in Stripe
        stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )
        
        # Update in DB
        await execute_sql(
            f"""
            UPDATE subscriptions
            SET status = 'pending_cancelation',
                updated_at = NOW()
            WHERE id = '{subscription_id}'
            """
        )
        
        return {"success": True}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/customers/{customer_id}/subscriptions")
async def get_customer_subscriptions(customer_id: str):
    """Get all subscriptions for customer."""
    try:
        res = await query_db(
            f"""
            SELECT 
                s.id, s.plan_id, s.status,
                s.current_period_start, s.current_period_end,
                p.name as plan_name, p.amount as plan_amount
            FROM subscriptions s
            JOIN plans p ON s.plan_id = p.id
            WHERE s.customer_id = '{customer_id}'
            ORDER BY s.created_at DESC
            """
        )
        
        return {"subscriptions": res.get("rows", [])}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/billing/run-cycle")
async def run_billing_cycle():
    """Trigger billing cycle (admin only)."""
    try:
        result = await service.run_billing_cycle()
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
