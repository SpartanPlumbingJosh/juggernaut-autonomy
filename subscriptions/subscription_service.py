"""
Subscription Management Service - Handles recurring billing, tiers, invoicing, and dunning.
"""
import datetime
import uuid
from typing import Optional, Dict, List
from dataclasses import dataclass

import stripe
import paypalrestsdk
from redis import Redis
from fastapi import HTTPException, status
from pydantic import BaseModel, validator

# Configuration
STRIPE_API_KEY = "your_stripe_api_key"
PAYPAL_MODE = "sandbox"  
PAYPAL_CLIENT_ID = "your_paypal_id"
PAYPAL_SECRET = "your_paypal_secret"

# Initialize payment processors
stripe.api_key = STRIPE_API_KEY
paypalrestsdk.configure({
    "mode": PAYPAL_MODE,
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_SECRET
})

@dataclass
class SubscriptionPlan:
    id: str
    name: str
    price_cents: int
    interval: str  # month/year
    features: List[str]
    metadata: Optional[Dict] = None

class TieredPricing:
    def __init__(self):
        self.plans = {
            "basic": SubscriptionPlan(
                id="basic",
                name="Basic Plan",
                price_cents=9900,
                interval="month",
                features=["1000 credits/month", "Basic support"]
            ),
            "pro": SubscriptionPlan(
                id="pro",
                name="Professional Plan",
                price_cents=29900,
                interval="month",
                features=["5000 credits/month", "Priority support"]
            ),
            "enterprise": SubscriptionPlan(
                id="enterprise",
                name="Enterprise Plan",
                price_cents=99900,
                interval="month",
                features=["Unlimited credits", "24/7 support"]
            )
        }

class SubscriptionRequest(BaseModel):
    plan_id: str
    customer_id: str
    payment_method: str  # stripe/paypal
    billing_email: str
    
    @validator('plan_id')
    def validate_plan(cls, v):
        if v not in TIERED_PRICING.plans:
            raise ValueError("Invalid plan ID")
        return v

class SubscriptionService:
    def __init__(self, db_pool, redis: Redis):
        self.db = db_pool
        self.redis = redis
        self.tiers = TieredPricing()

    async def create_subscription(self, request: SubscriptionRequest) -> Dict:
        """Create a new subscription with payment processor"""
        plan = self.tiers.plans[request.plan_id]
        
        try:
            if request.payment_method == "stripe":
                return await self._create_stripe_subscription(request, plan)
            elif request.payment_method == "paypal":
                return await self._create_paypal_subscription(request, plan)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid payment method"
                )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Subscription creation failed: {str(e)}"
            )

    async def _create_stripe_subscription(self, request: SubscriptionRequest, plan: SubscriptionPlan) -> Dict:
        """Create Stripe subscription"""
        stripe_customer = stripe.Customer.create(email=request.billing_email)
        
        subscription = stripe.Subscription.create(
            customer=stripe_customer.id,
            items=[{"price": self._get_stripe_price_id(plan)}],
            expand=["latest_invoice.payment_intent"]
        )
        
        # Store in our database
        sub_id = str(uuid.uuid4())
        await self._store_subscription(
            sub_id=sub_id,
            customer_id=request.customer_id,
            plan_id=plan.id,
            external_id=subscription.id,
            status='active'
        )
        
        return {
            "subscription_id": sub_id,
            "client_secret": subscription.latest_invoice.payment_intent.client_secret,
            "status": "requires_confirmation"
        }

    def _get_stripe_price_id(self, plan: SubscriptionPlan) -> str:
        """Get or create Stripe price ID for plan"""
        # Implementation would look up existing or create new price in Stripe
        pass

    async def _store_subscription(self, **kwargs):
        """Persist subscription to database"""
        # Implementation would store in PostgreSQL 
        pass

TIERED_PRICING = TieredPricing()
