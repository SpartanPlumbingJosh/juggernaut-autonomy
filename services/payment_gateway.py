"""
Payment Gateway Interface - Abstract base class for payment processors.
"""

from abc import ABC, abstractmethod
from typing import Dict

class PaymentGateway(ABC):
    """Abstract base class for payment gateways."""
    
    @abstractmethod
    async def process_payment(self, amount: float, currency: str, payment_method: str) -> Dict:
        """Process a payment transaction."""
        pass
        
    @abstractmethod
    async def process_refund(self, amount: float, currency: str, original_transaction_id: str) -> Dict:
        """Process a refund transaction."""
        pass

class StripeGateway(PaymentGateway):
    """Stripe payment gateway implementation."""
    
    def __init__(self):
        import stripe
        self.stripe = stripe
        self.stripe.api_key = "sk_test_..."  # Should be from config
        
    async def process_payment(self, amount: float, currency: str, payment_method: str) -> Dict:
        """Process payment through Stripe."""
        try:
            intent = self.stripe.PaymentIntent.create(
                amount=int(amount * 100),
                currency=currency,
                payment_method=payment_method,
                confirm=True,
                capture_method="automatic"
            )
            return {
                "success": True,
                "payment_id": intent.id,
                "status": intent.status
            }
        except self.stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
            
    async def process_refund(self, amount: float, currency: str, original_transaction_id: str) -> Dict:
        """Process refund through Stripe."""
        try:
            refund = self.stripe.Refund.create(
                payment_intent=original_transaction_id,
                amount=int(amount * 100)
            )
            return {
                "success": True,
                "refund_id": refund.id,
                "status": refund.status
            }
        except self.stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
