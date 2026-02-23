from typing import Dict, Optional
from decimal import Decimal
from .models import PaymentIntent, PaymentIntentStatus

class PaymentProcessor:
    async def create_payment_intent(self, amount: Decimal, currency: str, customer_id: str) -> PaymentIntent:
        """Create a new payment intent"""
        pass

    async def confirm_payment_intent(self, payment_intent_id: str) -> PaymentIntent:
        """Confirm a payment intent"""
        pass

    async def capture_payment_intent(self, payment_intent_id: str) -> PaymentIntent:
        """Capture a payment intent"""
        pass

    async def cancel_payment_intent(self, payment_intent_id: str) -> PaymentIntent:
        """Cancel a payment intent"""
        pass

    async def handle_webhook(self, payload: Dict) -> Optional[Dict]:
        """Process webhook events from payment processor"""
        pass
