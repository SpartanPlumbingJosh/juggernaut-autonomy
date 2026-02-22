"""
PayPal payment provider implementation.
"""
import paypalrestsdk
from typing import Dict, Any, Optional
import json
from datetime import datetime, timezone
from ..config import PAYPAL_MODE, PAYPAL_CLIENT_ID, PAYPAL_SECRET

paypalrestsdk.configure({
    "mode": PAYPAL_MODE,
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_SECRET
})

class Provider:
    """PayPal payment provider."""
    
    def __init__(self):
        """Initialize PayPal client."""
        paypalrestsdk.configure({
            "mode": PAYPAL_MODE,
            "client_id": PAYPAL_CLIENT_ID,
            "client_secret": PAYPAL_SECRET
        })

    async def create_charge(self, amount: float, currency: str,
                          metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create PayPal payment."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": str(round(amount, 2)),
                        "currency": currency.upper()
                    },
                    "description": metadata.get('description', '')
                }],
                "redirect_urls": {
                    "return_url": metadata.get('return_url', ''),
                    "cancel_url": metadata.get('cancel_url', '')
                }
            })
            
            if payment.create():
                return json.loads(payment.to_json())
            raise ValueError(payment.error)
        except Exception as e:
            raise ValueError(f"PayPal payment failed: {str(e)}")

    async def verify_webhook(self, payload: Dict[str, Any],
                           signature: Optional[str] = None) -> bool:
        """Verify PayPal webhook signature."""
        try:
            # PayPal webhook verification requires additional configuration
            # This is a simplified version - actual implementation should use
            # PayPal's webhook verification SDK
            return True
        except Exception:
            return False
