import stripe
import os
from typing import Optional, Dict
from fastapi import HTTPException

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class PaymentService:
    @staticmethod
    def create_customer(email: str, name: str = None) -> Dict:
        try:
            return stripe.Customer.create(
                email=email,
                name=name,
            )
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def create_payment_intent(amount: int, currency: str, customer_id: str, metadata: Optional[Dict] = None) -> Dict:
        try:
            return stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                automatic_payment_methods={"enabled": True},
                metadata=metadata or {},
            )
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def create_subscription(customer_id: str, price_id: str) -> Dict:
        try:
            return stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
            )
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))
