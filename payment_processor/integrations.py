"""
Payment processor integrations with PCI compliant providers.
Supports Stripe, PayPal, and manual payment tracking.
"""
from enum import Enum
import logging
from typing import Dict, Optional
import stripe

class PaymentProvider(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"
    MANUAL = "manual"

class PaymentProcessor:
    def __init__(self, provider: PaymentProvider, api_key: Optional[str] = None):
        self.provider = provider
        self.logger = logging.getLogger(__name__)
        
        if provider == PaymentProvider.STRIPE:
            if not api_key:
                raise ValueError("Stripe requires API key")
            stripe.api_key = api_key
            self.client = stripe

    def create_customer(self, email: str, name: str, **metadata) -> Dict:
        """Create a customer record in payment provider."""
        if self.provider == PaymentProvider.STRIPE:
            return self.client.Customer.create(
                email=email,
                name=name,
                metadata=metadata
            )
        raise NotImplementedError(f"Provider {self.provider} not implemented")

    def create_subscription(self, customer_id: str, plan_id: str) -> Dict:
        """Create recurring subscription."""
        if self.provider == PaymentProvider.STRIPE:
            return self.client.Subscription.create(
                customer=customer_id,
                items=[{"plan": plan_id}]
            )
        raise NotImplementedError(f"Provider {self.provider} not implemented")

    def charge_card(self, amount: int, currency: str, customer_id: str, description: str) -> Dict:
        """Process one-time payment."""
        if self.provider == PaymentProvider.STRIPE:
            return self.client.Charge.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                description=description
            )
        raise NotImplementedError(f"Provider {self.provider} not implemented")

    def refund_payment(self, charge_id: str) -> Dict:
        """Process refund."""
        if self.provider == PaymentProvider.STRIPE:
            return self.client.Refund.create(charge=charge_id)
        raise NotImplementedError(f"Provider {self.provider} not implemented")
