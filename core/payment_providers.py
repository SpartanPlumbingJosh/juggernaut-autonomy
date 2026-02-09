"""
Payment Providers - Interface with external payment processors.
"""
import stripe
from typing import Any, Dict, Optional

class PaymentProvider:
    def __init__(self):
        self.stripe = stripe
        self.stripe.api_key = "sk_test_..."  # Should be from config

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: str) -> Dict[str, Any]:
        """Create a subscription with payment provider."""
        try:
            subscription = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{"plan": plan_id}],
                default_payment_method=payment_method,
                expand=["latest_invoice.payment_intent"]
            )
            return subscription
        except self.stripe.error.StripeError as e:
            raise Exception(f"Payment provider error: {str(e)}")

    async def process_payment(self, amount: float, currency: str, customer_id: str) -> Dict[str, Any]:
        """Process a payment."""
        try:
            payment_intent = self.stripe.PaymentIntent.create(
                amount=int(amount * 100),
                currency=currency,
                customer=customer_id,
                payment_method_types=["card"]
            )
            return payment_intent
        except self.stripe.error.StripeError as e:
            raise Exception(f"Payment processing error: {str(e)}")

    async def generate_invoice(self, subscription_id: str) -> Dict[str, Any]:
        """Generate an invoice."""
        try:
            invoice = self.stripe.Invoice.create(
                subscription=subscription_id,
                auto_advance=True
            )
            return invoice
        except self.stripe.error.StripeError as e:
            raise Exception(f"Invoice generation error: {str(e)}")
