from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from core.payment_processor import PaymentProcessor

class SubscriptionManager:
    """Manages subscriptions and recurring billing."""
    
    def __init__(self):
        self.processor = PaymentProcessor()
        
    def create_subscription(self, customer_id: str, plan_id: str, 
                          trial_days: int = 0) -> Dict:
        """Create a new subscription."""
        result = self.processor.create_subscription(customer_id, plan_id)
        if not result["success"]:
            return result
            
        subscription = result["subscription"]
        return {
            "success": True,
            "subscription_id": subscription.id,
            "status": subscription.status,
            "current_period_end": subscription.current_period_end,
            "trial_end": subscription.trial_end
        }
        
    def cancel_subscription(self, subscription_id: str) -> Dict:
        """Cancel an existing subscription."""
        try:
            subscription = stripe.Subscription.delete(subscription_id)
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "canceled_at": subscription.canceled_at
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    def update_subscription(self, subscription_id: str, 
                          new_plan_id: str) -> Dict:
        """Update subscription plan."""
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                items=[{"price": new_plan_id}]
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    def list_subscriptions(self, customer_id: str) -> List[Dict]:
        """List all subscriptions for a customer."""
        try:
            subscriptions = stripe.Subscription.list(customer=customer_id)
            return [{
                "id": sub.id,
                "status": sub.status,
                "current_period_end": sub.current_period_end,
                "plan_id": sub.items.data[0].price.id
            } for sub in subscriptions.data]
        except stripe.error.StripeError as e:
            return []
            
    def generate_upcoming_invoice(self, subscription_id: str) -> Dict:
        """Generate preview of upcoming invoice."""
        try:
            invoice = stripe.Invoice.upcoming(subscription=subscription_id)
            return {
                "success": True,
                "amount_due": invoice.amount_due,
                "currency": invoice.currency,
                "due_date": invoice.due_date
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
