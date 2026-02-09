"""
Payment processor integrations (Stripe, Paddle, etc).
"""
import os
from typing import Any, Dict, Optional

import stripe
import paddle

class PaymentProcessor:
    """Base class for payment processors."""
    
    def __init__(self):
        self.configured = False
    
    def charge(self, amount: float, customer_id: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        raise NotImplementedError
        
    def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

class StripeProcessor(PaymentProcessor):
    """Stripe payment processor."""
    
    def __init__(self):
        super().__init__()
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        self.configured = bool(stripe.api_key)
    
    def charge(self, amount: float, customer_id: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        metadata = metadata or {}
        try:
            payment = stripe.PaymentIntent.create(
                amount=int(amount * 100),
                currency="usd",
                customer=customer_id,
                metadata=metadata,
                confirm=True
            )
            return {
                "success": True,
                "payment_id": payment.id,
                "status": payment.status
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e),
                "status": "failed"
            }
    
    def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        event = stripe.Event.construct_from(payload, stripe.api_key)
        
        if event.type == "payment_intent.succeeded":
            payment = event.data.object
            return {
                "event": "payment_succeeded",
                "payment_id": payment.id,
                "amount": payment.amount / 100,
                "customer_id": payment.customer
            }
        
        return {"event": "unhandled", "type": event.type}

class PaddleProcessor(PaymentProcessor):
    """Paddle payment processor."""
    
    def __init__(self):
        super().__init__()
        paddle.set_api_key(os.getenv("PADDLE_SECRET_KEY"))
        self.configured = bool(os.getenv("PADDLE_SECRET_KEY"))
    
    def charge(self, amount: float, customer_id: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        metadata = metadata or {}
        try:
            payment = paddle.Payment.create(
                amount=amount,
                currency="USD",
                customer_id=customer_id,
                metadata=metadata
            )
            return {
                "success": True,
                "payment_id": payment.id,
                "status": payment.status
            }
        except paddle.PaddleError as e:
            return {
                "success": False,
                "error": str(e),
                "status": "failed"
            }
    
    def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if payload.get("alert_name") == "payment_succeeded":
            return {
                "event": "payment_succeeded",
                "payment_id": payload["checkout_id"],
                "amount": float(payload["sale_gross"]),
                "customer_id": payload["customer_id"]
            }
        
        return {"event": "unhandled", "type": payload.get("alert_name")}

def get_processor(name: str = "stripe") -> PaymentProcessor:
    """Get configured payment processor."""
    processors = {
        "stripe": StripeProcessor,
        "paddle": PaddleProcessor
    }
    return processors.get(name.lower(), StripeProcessor)()
