"""
Subscription Manager - Handle subscription lifecycle and billing.
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
from billing.payment_processor import PaymentProcessor

class SubscriptionManager:
    """Manage subscriptions and billing."""
    
    def __init__(self):
        self.payment_processor = PaymentProcessor()
        
    async def create_customer(self, email: str, payment_method_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                payment_method=payment_method_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                },
                metadata=metadata
            )
            return {
                "success": True,
                "customer_id": customer.id
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a subscription."""
        try:
            subscription = stripe.Subscription.delete(subscription_id)
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def update_subscription(self, subscription_id: str, price_id: str) -> Dict[str, Any]:
        """Update subscription plan."""
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                items=[{
                    'id': subscription['items']['data'][0].id,
                    'price': price_id,
                }]
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def get_subscription_status(self, subscription_id: str) -> Dict[str, Any]:
        """Get subscription status."""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return {
                "success": True,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
