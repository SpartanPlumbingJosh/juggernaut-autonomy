import os
import stripe
from typing import Dict, Optional
from fastapi import HTTPException

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class StripeService:
    def __init__(self):
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    async def create_customer(self, email: str, name: str) -> Dict:
        try:
            return stripe.Customer.create(
                email=email,
                name=name,
                description=f"Customer for {email}"
            )
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        try:
            return stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                expand=["latest_invoice.payment_intent"]
            )
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Optional[Dict]:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            # Handle specific events
            if event['type'] == 'invoice.payment_succeeded':
                return self._handle_payment_succeeded(event)
            elif event['type'] == 'customer.subscription.deleted':
                return self._handle_subscription_cancelled(event)
            
            return None
        except stripe.error.SignatureVerificationError as e:
            raise HTTPException(status_code=400, detail=str(e))

    def _handle_payment_succeeded(self, event: Dict) -> Dict:
        # Handle successful payment
        invoice = event['data']['object']
        customer_id = invoice['customer']
        amount_paid = invoice['amount_paid']
        # Update your database here
        return {"status": "success", "customer_id": customer_id}

    def _handle_subscription_cancelled(self, event: Dict) -> Dict:
        # Handle subscription cancellation
        subscription = event['data']['object']
        customer_id = subscription['customer']
        # Update your database here
        return {"status": "cancelled", "customer_id": customer_id}
