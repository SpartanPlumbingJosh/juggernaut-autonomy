from datetime import datetime, timedelta
from typing import Dict, Optional
from enum import Enum
import stripe
import paypalrestsdk

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAUSED = "paused"
    TRIAL = "trial"

class SubscriptionManager:
    def __init__(self):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        paypalrestsdk.configure({
            "mode": os.getenv("PAYPAL_MODE", "sandbox"),
            "client_id": os.getenv("PAYPAL_CLIENT_ID"),
            "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
        })

    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        provider: PaymentProvider,
        trial_days: int = 0
    ) -> Tuple[bool, Dict]:
        """Create new subscription"""
        try:
            if provider == PaymentProvider.STRIPE:
                subscription = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{"plan": plan_id}],
                    trial_period_days=trial_days
                )
                return True, {
                    "subscription_id": subscription.id,
                    "status": subscription.status,
                    "current_period_end": datetime.fromtimestamp(subscription.current_period_end)
                }
            
            elif provider == PaymentProvider.PAYPAL:
                agreement = paypalrestsdk.BillingAgreement({
                    "name": "Subscription Agreement",
                    "description": "Recurring Payment",
                    "start_date": (datetime.utcnow() + timedelta(days=trial_days)).isoformat() + "Z",
                    "plan": {"id": plan_id},
                    "payer": {"payment_method": "paypal"}
                })
                if agreement.create():
                    return True, {
                        "agreement_id": agreement.id,
                        "status": agreement.state,
                        "start_date": datetime.strptime(agreement.start_date, "%Y-%m-%dT%H:%M:%SZ")
                    }
                return False, {"error": agreement.error}
            
            return False, {"error": "Invalid payment provider"}
        except Exception as e:
            return False, {"error": str(e)}

    async def cancel_subscription(
        self,
        subscription_id: str,
        provider: PaymentProvider
    ) -> Tuple[bool, Dict]:
        """Cancel subscription"""
        try:
            if provider == PaymentProvider.STRIPE:
                subscription = stripe.Subscription.delete(subscription_id)
                return True, {"status": subscription.status}
            
            elif provider == PaymentProvider.PAYPAL:
                agreement = paypalrestsdk.BillingAgreement.find(subscription_id)
                if agreement.cancel({"note": "Customer requested cancellation"}):
                    return True, {"status": agreement.state}
                return False, {"error": agreement.error}
            
            return False, {"error": "Invalid payment provider"}
        except Exception as e:
            return False, {"error": str(e)}

    async def update_subscription(
        self,
        subscription_id: str,
        provider: PaymentProvider,
        new_plan_id: Optional[str] = None,
        quantity: Optional[int] = None
    ) -> Tuple[bool, Dict]:
        """Update subscription details"""
        try:
            if provider == PaymentProvider.STRIPE:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    items=[{"plan": new_plan_id}] if new_plan_id else None,
                    quantity=quantity
                )
                return True, {
                    "subscription_id": subscription.id,
                    "status": subscription.status,
                    "current_period_end": datetime.fromtimestamp(subscription.current_period_end)
                }
            
            elif provider == PaymentProvider.PAYPAL:
                agreement = paypalrestsdk.BillingAgreement.find(subscription_id)
                if new_plan_id:
                    agreement.plan = {"id": new_plan_id}
                if agreement.update():
                    return True, {
                        "agreement_id": agreement.id,
                        "status": agreement.state
                    }
                return False, {"error": agreement.error}
            
            return False, {"error": "Invalid payment provider"}
        except Exception as e:
            return False, {"error": str(e)}
