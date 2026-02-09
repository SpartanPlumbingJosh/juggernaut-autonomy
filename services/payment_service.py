import os
import stripe
from datetime import datetime, timezone
from typing import Dict, Optional, List

stripe.api_key = os.getenv('STRIPE_API_KEY')

class PaymentService:
    """Handles all payment processing and subscription management with Stripe."""
    
    @staticmethod
    async def create_customer(email: str, name: str = None) -> Dict:
        """Create a Stripe customer"""
        return stripe.Customer.create(
            email=email,
            name=name,
            metadata={"created_at": datetime.now(timezone.utc).isoformat()}
        )

    @staticmethod
    async def create_subscription(
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create a subscription for a customer"""
        return stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            metadata=metadata or {},
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"]
        )

    @staticmethod
    async def record_payment_event(
        event_id: str,
        amount: int,
        currency: str,
        event_type: str,
        metadata: Dict
    ) -> Dict:
        """Record a revenue/cost event in our system"""
        metadata.update({
            "stripe_event_id": event_id,
            "recorded_at": datetime.now(timezone.utc).isoformat()  
        })
        
        return {
            "event_type": event_type,
            "amount_cents": amount,
            "currency": currency.lower(),
            "metadata": metadata,
            "source": "stripe"
        }

    @staticmethod
    async def list_products() -> List[Dict]:
        """List available products/subscription plans"""
        return stripe.Product.list(active=True)

    @staticmethod
    async def get_invoice_pdf(invoice_id: str) -> bytes:
        """Retrieve invoice PDF"""
        invoice = stripe.Invoice.retrieve(invoice_id)
        return stripe.File.retrieve(invoice.invoice_pdf).contents
