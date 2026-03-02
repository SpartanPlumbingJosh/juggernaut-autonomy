from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import uuid
from datetime import datetime

from services.payment.models import (
    PaymentIntent,
    PaymentMethod,
    Subscription,
    Invoice
)

class PaymentProcessor(ABC):
    """Base class for payment processors."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
    @abstractmethod
    async def create_payment_intent(
        self,
        amount: int,
        currency: str,
        customer_id: str,
        payment_method: Optional[PaymentMethod] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PaymentIntent:
        """Create a payment intent."""
        pass
        
    @abstractmethod
    async def create_subscription(
        self,
        plan_id: str,
        customer_id: str,
        payment_method: Optional[PaymentMethod] = None,
        trial_days: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Subscription:
        """Create a subscription."""
        pass
        
    @abstractmethod
    async def generate_invoice(
        self,
        customer_id: str,
        items: List[Dict[str, Any]],
        due_date: Optional[datetime] = None
    ) -> Invoice:
        """Generate an invoice."""
        pass
        
    @abstractmethod
    async def verify_webhook(
        self,
        payload: Dict[str, Any],
        signature: str
    ) -> bool:
        """Verify webhook signature."""
        pass

class StripeProcessor(PaymentProcessor):
    """Stripe payment processor implementation."""
    
    async def create_payment_intent(self, amount, currency, customer_id, payment_method=None, metadata=None):
        """Stripe-specific payment intent creation."""
        # Implementation using Stripe API
        return PaymentIntent(
            id=f"pi_{uuid.uuid4().hex}",
            amount=amount,
            currency=currency,
            status="requires_payment_method",
            metadata=metadata,
            payment_method=payment_method
        )

class PayPalProcessor(PaymentProcessor):
    """PayPal payment processor implementation."""
    pass

class CryptoProcessor(PaymentProcessor):
    """Cryptocurrency payment processor implementation."""
    pass
