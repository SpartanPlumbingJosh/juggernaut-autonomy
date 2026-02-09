import os
import stripe
import paypalrestsdk
from datetime import datetime
from typing import Dict, Optional, List, Any
from enum import Enum

class PaymentGateway(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"

class PaymentStatus(Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"

class PaymentGatewayClient:
    def __init__(self):
        # Initialize Stripe
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        self.stripe = stripe
        
        # Initialize PayPal
        paypalrestsdk.configure({
            "mode": os.getenv("PAYPAL_MODE", "sandbox"),
            "client_id": os.getenv("PAYPAL_CLIENT_ID"),
            "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
        })
        self.paypal = paypalrestsdk

    async def create_payment(self, amount: float, currency: str, gateway: PaymentGateway, 
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a payment intent"""
        metadata = metadata or {}
        amount_cents = int(amount * 100)
        
        if gateway == PaymentGateway.STRIPE:
            try:
                intent = self.stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=currency,
                    metadata=metadata,
                    automatic_payment_methods={"enabled": True},
                )
                return {
                    "success": True,
                    "payment_id": intent.id,
                    "client_secret": intent.client_secret,
                    "status": PaymentStatus.PENDING.value
                }
            except self.stripe.error.StripeError as e:
                return {"success": False, "error": str(e)}
                
        elif gateway == PaymentGateway.PAYPAL:
            try:
                payment = self.paypal.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": f"{amount:.2f}",
                            "currency": currency
                        },
                        "description": metadata.get("description", "")
                    }],
                    "redirect_urls": {
                        "return_url": os.getenv("PAYPAL_RETURN_URL"),
                        "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                    }
                })
                
                if payment.create():
                    return {
                        "success": True,
                        "payment_id": payment.id,
                        "approval_url": next(link.href for link in payment.links if link.method == "REDIRECT"),
                        "status": PaymentStatus.PENDING.value
                    }
                return {"success": False, "error": payment.error}
            except Exception as e:
                return {"success": False, "error": str(e)}
                
        return {"success": False, "error": "Unsupported payment gateway"}

    async def handle_webhook(self, payload: Dict[str, Any], gateway: PaymentGateway) -> Dict[str, Any]:
        """Process payment webhook events"""
        if gateway == PaymentGateway.STRIPE:
            try:
                event = self.stripe.Webhook.construct_event(
                    payload,
                    os.getenv("STRIPE_WEBHOOK_SECRET"),
                    tolerance=300
                )
                
                if event.type == "payment_intent.succeeded":
                    return self._handle_success(event.data.object)
                elif event.type == "payment_intent.payment_failed":
                    return self._handle_failure(event.data.object)
                elif event.type == "charge.refunded":
                    return self._handle_refund(event.data.object)
                    
            except self.stripe.error.SignatureVerificationError as e:
                return {"success": False, "error": str(e)}
                
        elif gateway == PaymentGateway.PAYPAL:
            try:
                event = payload
                if event.get("event_type") == "PAYMENT.SALE.COMPLETED":
                    return self._handle_success(event)
                elif event.get("event_type") == "PAYMENT.SALE.DENIED":
                    return self._handle_failure(event)
                elif event.get("event_type") == "PAYMENT.SALE.REFUNDED":
                    return self._handle_refund(event)
                    
            except Exception as e:
                return {"success": False, "error": str(e)}
                
        return {"success": False, "error": "Unsupported event type"}

    def _handle_success(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment"""
        return {
            "success": True,
            "payment_id": event_data.get("id"),
            "amount": event_data.get("amount") / 100 if event_data.get("amount") else None,
            "currency": event_data.get("currency"),
            "status": PaymentStatus.SUCCEEDED.value,
            "metadata": event_data.get("metadata", {})
        }

    def _handle_failure(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment"""
        return {
            "success": True,
            "payment_id": event_data.get("id"),
            "status": PaymentStatus.FAILED.value,
            "error": event_data.get("last_payment_error", {}).get("message", "Payment failed")
        }

    def _handle_refund(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle refund"""
        return {
            "success": True,
            "payment_id": event_data.get("id"),
            "status": PaymentStatus.REFUNDED.value,
            "refund_amount": event_data.get("amount_refunded", 0) / 100,
            "currency": event_data.get("currency")
        }
