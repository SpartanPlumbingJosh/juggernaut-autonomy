"""
Payment Gateway Integration - Handle transactions with external payment processors.
Supports Stripe, PayPal, and direct bank transfers.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

class PaymentGateway:
    def __init__(self, provider: str, api_key: str):
        self.provider = provider
        self.api_key = api_key
        
    async def create_payment_intent(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payment intent with the gateway."""
        # Implementation would vary by provider
        return {
            "payment_intent_id": "pi_123",
            "client_secret": "secret_123",
            "status": "requires_payment_method",
            "created": datetime.utcnow().isoformat()
        }
        
    async def capture_payment(self, payment_intent_id: str) -> Dict[str, Any]:
        """Capture an authorized payment."""
        return {
            "payment_intent_id": payment_intent_id,
            "status": "succeeded",
            "captured_at": datetime.utcnow().isoformat()
        }
        
    async def refund_payment(self, payment_intent_id: str, amount: float) -> Dict[str, Any]:
        """Refund a captured payment."""
        return {
            "refund_id": "re_123",
            "payment_intent_id": payment_intent_id,
            "amount": amount,
            "status": "succeeded",
            "refunded_at": datetime.utcnow().isoformat()
        }
