import stripe
from typing import Optional, Dict
from datetime import datetime
from fastapi import HTTPException

class PaymentService:
    def __init__(self, api_key: str):
        stripe.api_key = api_key

    async def create_customer(self, email: str, name: str) -> Dict:
        """Create a new Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"created_at": datetime.utcnow().isoformat()}
            )
            return {
                "id": customer.id,
                "email": customer.email,
                "status": "created"
            }
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        payment_method_id: Optional[str] = None
    ) -> Dict:
        """Create a new subscription"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret,
                "status": subscription.status
            }
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def handle_webhook(self, payload: bytes, sig_header: str, webhook_secret: str) -> Dict:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'invoice.payment_succeeded':
                await self._handle_payment_success(event)
            elif event['type'] == 'customer.subscription.updated':
                await self._handle_subscription_update(event)
                
            return {"status": "processed"}
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def _handle_payment_success(self, event: Dict) -> None:
        """Handle successful payment"""
        invoice = event['data']['object']
        customer_id = invoice['customer']
        amount_paid = invoice['amount_paid']
        # Update user's access in your database

    async def _handle_subscription_update(self, event: Dict) -> None:
        """Handle subscription changes"""
        subscription = event['data']['object']
        customer_id = subscription['customer']
        status = subscription['status']
        # Update subscription status in DB
