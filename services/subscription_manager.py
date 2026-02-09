from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from enum import Enum
import stripe
from fastapi import HTTPException

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"

class SubscriptionManager:
    """Handle subscription lifecycle and billing"""
    
    def __init__(self):
        self.dunning_attempts = 3
        self.dunning_interval = timedelta(days=3)
    
    async def create_subscription(self, customer_id: str, plan_id: str, trial_days: int = 0) -> Dict[str, Any]:
        """Create new subscription"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id}],
                trial_period_days=trial_days,
                expand=["latest_invoice.payment_intent"]
            )
            
            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_end": datetime.utcfromtimestamp(subscription.current_period_end).isoformat(),
                "trial_end": datetime.utcfromtimestamp(subscription.trial_end).isoformat() if subscription.trial_end else None
            }
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    async def handle_dunning(self, subscription_id: str) -> Dict[str, Any]:
        """Handle failed payment and retry logic"""
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        if subscription.status != SubscriptionStatus.PAST_DUE:
            return {"status": "not_past_due"}
        
        # Attempt to collect payment
        try:
            invoice = stripe.Invoice.retrieve(subscription.latest_invoice)
            payment_intent = stripe.PaymentIntent.retrieve(invoice.payment_intent)
            
            if payment_intent.status == "requires_payment_method":
                # Attempt to collect payment with customer's default payment method
                payment_intent = stripe.PaymentIntent.confirm(
                    payment_intent.id,
                    payment_method=subscription.default_payment_method
                )
                
                if payment_intent.status == "succeeded":
                    return {"status": "payment_collected"}
                
        except stripe.error.StripeError as e:
            pass
        
        # If still unpaid after retries, cancel subscription
        if subscription.dunning_count >= self.dunning_attempts:
            await self.cancel_subscription(subscription_id)
            return {"status": "canceled"}
        
        return {"status": "retry_scheduled"}
    
    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel subscription"""
        try:
            subscription = stripe.Subscription.delete(subscription_id)
            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "canceled_at": datetime.utcfromtimestamp(subscription.canceled_at).isoformat()
            }
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))
