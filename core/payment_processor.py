import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Optional, List
import json
import logging

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self, stripe_api_key: str, paypal_client_id: str, paypal_secret: str):
        stripe.api_key = stripe_api_key
        paypalrestsdk.configure({
            "mode": "live",
            "client_id": paypal_client_id,
            "client_secret": paypal_secret
        })
        
    async def create_customer(self, email: str, payment_method: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new customer in payment systems"""
        try:
            if payment_method == "stripe":
                customer = stripe.Customer.create(
                    email=email,
                    metadata=metadata or {}
                )
                return {"success": True, "customer_id": customer.id}
            elif payment_method == "paypal":
                # PayPal doesn't have direct customer objects
                return {"success": True, "customer_id": email}
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: str) -> Dict:
        """Create a new subscription"""
        try:
            if payment_method == "stripe":
                sub = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{"price": plan_id}],
                    expand=["latest_invoice.payment_intent"]
                )
                return {
                    "success": True,
                    "subscription_id": sub.id,
                    "status": sub.status,
                    "current_period_end": sub.current_period_end
                }
            elif payment_method == "paypal":
                agreement = paypalrestsdk.BillingAgreement({
                    "name": "Subscription Agreement",
                    "description": "Recurring subscription",
                    "start_date": datetime.now(timezone.utc).isoformat(),
                    "plan": {
                        "id": plan_id
                    },
                    "payer": {
                        "payment_method": "paypal"
                    }
                })
                if agreement.create():
                    return {
                        "success": True,
                        "subscription_id": agreement.id,
                        "status": agreement.state,
                        "current_period_end": agreement.start_date
                    }
                return {"success": False, "error": agreement.error}
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def handle_webhook(self, payload: Dict, signature: Optional[str] = None, source: str = "stripe") -> Dict:
        """Process payment webhooks"""
        try:
            event = None
            if source == "stripe":
                event = stripe.Webhook.construct_event(
                    json.dumps(payload),
                    signature,
                    stripe.WebhookEndpoint.secret
                )
            elif source == "paypal":
                event = paypalrestsdk.WebhookEvent.verify(
                    json.dumps(payload),
                    signature
                )
                
            if not event:
                return {"success": False, "error": "Invalid event"}
                
            event_type = event.get("type")
            data = event.get("data", {})
            
            # Handle different event types
            if event_type in ["invoice.payment_succeeded", "PAYMENT.SALE.COMPLETED"]:
                await self._handle_payment_success(data)
            elif event_type in ["customer.subscription.deleted", "BILLING.SUBSCRIPTION.CANCELLED"]:
                await self._handle_subscription_cancelled(data)
            elif event_type in ["invoice.payment_failed", "PAYMENT.SALE.DENIED"]:
                await self._handle_payment_failed(data)
                
            return {"success": True}
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def _handle_payment_success(self, data: Dict) -> None:
        """Handle successful payment"""
        # Implement logic to provision services, update database, etc
        pass
        
    async def _handle_subscription_cancelled(self, data: Dict) -> None:
        """Handle subscription cancellation"""
        # Implement logic to deprovision services, update database, etc
        pass
        
    async def _handle_payment_failed(self, data: Dict) -> None:
        """Handle failed payment"""
        # Implement logic to notify customer, retry payment, etc
        pass
