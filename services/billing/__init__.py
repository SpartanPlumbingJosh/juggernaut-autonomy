"""
Billing Service - Handles subscription management and invoicing.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import stripe

class BillingService:
    def __init__(self, config: Dict[str, Any]):
        self.stripe_key = config.get("stripe_secret_key")
        if self.stripe_key:
            stripe.api_key = self.stripe_key

    async def create_customer(self, email: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new customer in Stripe."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name or "",
                description=f"Customer created on {datetime.utcnow().isoformat()}"
            )
            return {
                "success": True,
                "customer_id": customer.id
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a subscription."""
        try:
            subscription = stripe.Subscription.delete(subscription_id)
            return {
                "success": True,
                "status": subscription.status,
                "cancelled_at": subscription.canceled_at
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def create_invoice(self, customer_id: str, amount: int, currency: str) -> Dict[str, Any]:
        """Create an invoice."""
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                auto_advance=True,
                collection_method='send_invoice',
                days_until_due=30,
                description=f"Invoice for {amount/100:.2f} {currency}"
            )
            return {
                "success": True,
                "invoice_id": invoice.id,
                "status": invoice.status
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
