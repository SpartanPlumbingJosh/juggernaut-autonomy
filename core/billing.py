from typing import Dict, Any
from datetime import datetime
import stripe

stripe.api_key = "your-stripe-secret-key"

class BillingManager:
    def __init__(self):
        self.webhook_secret = "your-stripe-webhook-secret"

    async def create_customer(self, email: str) -> Dict[str, Any]:
        try:
            customer = stripe.Customer.create(email=email)
            return {"customer_id": customer.id}
        except Exception as e:
            return {"error": str(e)}

    async def create_subscription(self, customer_id: str, plan_id: str) -> Dict[str, Any]:
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "payment_intent": subscription.latest_invoice.payment_intent
            }
        except Exception as e:
            return {"error": str(e)}

    async def handle_webhook(self, payload: str, sig_header: str) -> Dict[str, Any]:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'invoice.payment_succeeded':
                # Handle successful payment
                invoice = event['data']['object']
                return {"event": "payment_succeeded", "invoice_id": invoice.id}
                
            return {"event": event['type']}
        except Exception as e:
            return {"error": str(e)}
