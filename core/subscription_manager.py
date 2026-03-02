from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import logging
from core.payment_processor import PaymentProcessor

logger = logging.getLogger(__name__)

class SubscriptionManager:
    def __init__(self, payment_processor: PaymentProcessor):
        self.payment_processor = payment_processor
        
    async def create_subscription(self, customer_data: Dict, plan_id: str, payment_method: str) -> Dict:
        """Create a new subscription for a customer"""
        try:
            # Create customer in payment system
            customer_res = await self.payment_processor.create_customer(
                email=customer_data["email"],
                payment_method=payment_method,
                metadata={
                    "name": customer_data.get("name"),
                    "phone": customer_data.get("phone")
                }
            )
            
            if not customer_res["success"]:
                return {"success": False, "error": customer_res["error"]}
                
            # Create subscription
            sub_res = await self.payment_processor.create_subscription(
                customer_id=customer_res["customer_id"],
                plan_id=plan_id,
                payment_method=payment_method
            )
            
            if not sub_res["success"]:
                return {"success": False, "error": sub_res["error"]}
                
            # Store subscription in database
            # Implement your database storage logic here
            
            return {
                "success": True,
                "subscription_id": sub_res["subscription_id"],
                "status": sub_res["status"],
                "customer_id": customer_res["customer_id"]
            }
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def cancel_subscription(self, subscription_id: str, payment_method: str) -> Dict:
        """Cancel an existing subscription"""
        try:
            if payment_method == "stripe":
                stripe.Subscription.delete(subscription_id)
            elif payment_method == "paypal":
                agreement = paypalrestsdk.BillingAgreement.find(subscription_id)
                agreement.cancel({"note": "Customer requested cancellation"})
                
            # Update database status
            # Implement your database update logic here
            
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to cancel subscription: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def get_subscription_status(self, subscription_id: str, payment_method: str) -> Dict:
        """Get current subscription status"""
        try:
            status = None
            if payment_method == "stripe":
                sub = stripe.Subscription.retrieve(subscription_id)
                status = sub.status
            elif payment_method == "paypal":
                agreement = paypalrestsdk.BillingAgreement.find(subscription_id)
                status = agreement.state
                
            return {
                "success": True,
                "status": status,
                "subscription_id": subscription_id
            }
        except Exception as e:
            logger.error(f"Failed to get subscription status: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def list_subscriptions(self, customer_id: str, payment_method: str) -> Dict:
        """List all subscriptions for a customer"""
        try:
            subscriptions = []
            if payment_method == "stripe":
                subs = stripe.Subscription.list(customer=customer_id)
                subscriptions = [{
                    "id": s.id,
                    "status": s.status,
                    "current_period_end": s.current_period_end
                } for s in subs]
            elif payment_method == "paypal":
                # PayPal doesn't have direct customer-subscription mapping
                # Implement your own logic to map customers to subscriptions
                pass
                
            return {
                "success": True,
                "subscriptions": subscriptions
            }
        except Exception as e:
            logger.error(f"Failed to list subscriptions: {str(e)}")
            return {"success": False, "error": str(e)}
