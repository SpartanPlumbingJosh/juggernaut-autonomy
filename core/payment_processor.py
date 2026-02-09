import stripe
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import json
from decimal import Decimal

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.stripe = stripe
        
    async def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new Stripe customer."""
        return self.stripe.Customer.create(
            email=email,
            name=name,
            metadata=metadata or {}
        )
        
    async def create_subscription(self, customer_id: str, price_id: str, trial_days: int = 0) -> Dict:
        """Create a new subscription."""
        return self.stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            trial_period_days=trial_days,
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"]
        )
        
    async def cancel_subscription(self, subscription_id: str) -> Dict:
        """Cancel a subscription."""
        return self.stripe.Subscription.delete(subscription_id)
        
    async def update_subscription(self, subscription_id: str, new_price_id: str) -> Dict:
        """Update subscription to new pricing plan."""
        sub = self.stripe.Subscription.retrieve(subscription_id)
        return self.stripe.Subscription.modify(
            subscription_id,
            items=[{
                "id": sub["items"]["data"][0].id,
                "price": new_price_id
            }]
        )
        
    async def create_invoice(self, customer_id: str, amount: Decimal, currency: str, description: str) -> Dict:
        """Create a one-time invoice."""
        return self.stripe.Invoice.create(
            customer=customer_id,
            amount=int(amount * 100),  # Convert to cents
            currency=currency.lower(),
            description=description,
            auto_advance=True
        )
        
    async def record_usage(self, subscription_item_id: str, quantity: int, timestamp: datetime) -> Dict:
        """Record usage for metered billing."""
        return self.stripe.SubscriptionItem.create_usage_record(
            subscription_item_id,
            quantity=quantity,
            timestamp=int(timestamp.timestamp())
        )
        
    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Tuple[bool, Optional[Dict]]:
        """Process Stripe webhook event."""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            return True, event
        except Exception as e:
            return False, {"error": str(e)}
            
    async def retry_failed_payment(self, invoice_id: str) -> Dict:
        """Retry a failed payment."""
        return self.stripe.Invoice.pay(invoice_id)
        
    async def get_payment_methods(self, customer_id: str) -> List[Dict]:
        """Get customer's payment methods."""
        return self.stripe.PaymentMethod.list(
            customer=customer_id,
            type="card"
        )["data"]
        
    async def update_default_payment_method(self, customer_id: str, payment_method_id: str) -> Dict:
        """Update customer's default payment method."""
        return self.stripe.Customer.modify(
            customer_id,
            invoice_settings={"default_payment_method": payment_method_id}
        )
        
    async def get_invoices(self, customer_id: str, limit: int = 10) -> List[Dict]:
        """Get customer's invoices."""
        return self.stripe.Invoice.list(
            customer=customer_id,
            limit=limit
        )["data"]
        
    async def get_subscription(self, subscription_id: str) -> Dict:
        """Get subscription details."""
        return self.stripe.Subscription.retrieve(
            subscription_id,
            expand=["latest_invoice.payment_intent"]
        )
        
    async def get_upcoming_invoice(self, customer_id: str, subscription_id: Optional[str] = None) -> Dict:
        """Get upcoming invoice details."""
        return self.stripe.Invoice.upcoming(
            customer=customer_id,
            subscription=subscription_id
        )
