import stripe
from typing import Dict, Optional
from fastapi import HTTPException
from config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class PaymentGateway:
    @staticmethod
    async def create_customer(email: str, payment_method_id: Optional[str] = None) -> Dict:
        try:
            customer = stripe.Customer.create(
                email=email,
                payment_method=payment_method_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                } if payment_method_id else None
            )
            return customer
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def create_subscription(customer_id: str, price_id: str) -> Dict:
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return subscription
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def handle_webhook(payload: bytes, sig_header: str) -> Dict:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            return event
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            raise HTTPException(status_code=400, detail="Invalid signature")
