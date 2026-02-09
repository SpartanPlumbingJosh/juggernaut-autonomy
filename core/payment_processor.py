import os
import stripe
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

class PaymentMethod(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"

class PaymentProcessor:
    def __init__(self, stripe_api_key: Optional[str] = None):
        self.stripe_api_key = stripe_api_key or os.getenv('STRIPE_API_KEY')

    def create_customer(self, email: str, name: str) -> Dict[str, Any]:
        """Create a new payment customer."""
        stripe.api_key = self.stripe_api_key
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
            )
            return {
                "success": True,
                "customer_id": customer.id,
                "payment_method": PaymentMethod.STRIPE.value
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

    def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create recurring subscription."""
        stripe.api_key = self.stripe_api_key
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                metadata=metadata or {},
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

    def create_one_time_payment(
        self,
        amount: int,
        currency: str,
        description: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create single payment intent."""
        stripe.api_key = self.stripe_api_key
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                description=description,
                metadata=metadata or {},
            )
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

    def generate_invoice(
        self,
        customer_id: str,
        items: List[Dict[str, Any]],
        description: str = "",
        auto_advance: bool = True
    ) -> Dict[str, Any]:
        """Generate and send invoice."""
        stripe.api_key = self.stripe_api_key
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                description=description,
                auto_advance=auto_advance,
                collection_method="send_invoice",
                days_until_due=30,
                items=items,
            )
            return {
                "success": True,
                "invoice_id": invoice.id,
                "invoice_url": invoice.hosted_invoice_url,
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
