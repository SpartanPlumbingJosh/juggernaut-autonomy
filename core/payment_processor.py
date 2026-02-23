"""
Payment Processor Module - Handles all payment processing and revenue collection.

Features:
- Multi-provider integration (Stripe, PayPal, etc)
- Unified interface for transactions
- Webhook handling
- Payout management
"""

import os
from typing import Dict, Optional, Union
from enum import Enum
import stripe
import paypalrestsdk

class PaymentProvider(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"

class PaymentProcessor:
    def __init__(self):
        # Initialize payment providers
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        paypalrestsdk.configure({
            "mode": os.getenv("PAYPAL_MODE", "sandbox"),
            "client_id": os.getenv("PAYPAL_CLIENT_ID"),
            "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
        })

    async def create_payment_intent(
        self,
        amount: float,
        currency: str,
        provider: PaymentProvider = PaymentProvider.STRIPE,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create a payment intent with the specified provider."""
        try:
            if provider == PaymentProvider.STRIPE:
                intent = stripe.PaymentIntent.create(
                    amount=int(amount * 100),  # Convert to cents
                    currency=currency.lower(),
                    metadata=metadata or {}
                )
                return {
                    "success": True,
                    "client_secret": intent.client_secret,
                    "payment_id": intent.id
                }
            elif provider == PaymentProvider.PAYPAL:
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": str(amount),
                            "currency": currency.upper()
                        }
                    }],
                    "redirect_urls": {
                        "return_url": os.getenv("PAYPAL_RETURN_URL"),
                        "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                    }
                })
                if payment.create():
                    return {
                        "success": True,
                        "approval_url": next(
                            link.href for link in payment.links 
                            if link.method == "REDIRECT"
                        ),
                        "payment_id": payment.id
                    }
                return {"success": False, "error": payment.error}
            else:
                return {"success": False, "error": "Unsupported payment provider"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(
        self,
        provider: PaymentProvider,
        payload: Union[Dict, str],
        signature: Optional[str] = None
    ) -> Dict:
        """Process webhook events from payment providers."""
        try:
            if provider == PaymentProvider.STRIPE:
                event = stripe.Webhook.construct_event(
                    payload,
                    signature,
                    os.getenv("STRIPE_WEBHOOK_SECRET")
                )
                return self._process_stripe_event(event)
            elif provider == PaymentProvider.PAYPAL:
                if isinstance(payload, str):
                    payload = json.loads(payload)
                return self._process_paypal_event(payload)
            else:
                return {"success": False, "error": "Unsupported payment provider"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _process_stripe_event(self, event: Dict) -> Dict:
        """Process Stripe webhook event."""
        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})
        
        if event_type == "payment_intent.succeeded":
            return {
                "success": True,
                "event": "payment_success",
                "payment_id": data.get("id"),
                "amount": data.get("amount") / 100,
                "currency": data.get("currency")
            }
        elif event_type == "payment_intent.payment_failed":
            return {
                "success": True,
                "event": "payment_failed",
                "payment_id": data.get("id"),
                "error": data.get("last_payment_error", {}).get("message")
            }
        else:
            return {"success": True, "event": event_type}

    def _process_paypal_event(self, event: Dict) -> Dict:
        """Process PayPal webhook event."""
        event_type = event.get("event_type")
        resource = event.get("resource", {})
        
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            return {
                "success": True,
                "event": "payment_success",
                "payment_id": resource.get("id"),
                "amount": float(resource.get("amount", {}).get("value", 0)),
                "currency": resource.get("amount", {}).get("currency_code")
            }
        elif event_type == "PAYMENT.CAPTURE.DENIED":
            return {
                "success": True,
                "event": "payment_failed",
                "payment_id": resource.get("id"),
                "error": resource.get("details", {}).get("description")
            }
        else:
            return {"success": True, "event": event_type}

    async def issue_refund(
        self,
        payment_id: str,
        provider: PaymentProvider,
        amount: Optional[float] = None
    ) -> Dict:
        """Issue a refund for a payment."""
        try:
            if provider == PaymentProvider.STRIPE:
                refund = stripe.Refund.create(
                    payment_intent=payment_id,
                    amount=int(amount * 100) if amount else None
                )
                return {
                    "success": True,
                    "refund_id": refund.id,
                    "status": refund.status
                }
            elif provider == PaymentProvider.PAYPAL:
                payment = paypalrestsdk.Payment.find(payment_id)
                sale = payment.transactions[0].related_resources[0].sale
                refund = sale.refund({
                    "amount": {
                        "total": str(amount) if amount else sale.amount.total,
                        "currency": sale.amount.currency
                    }
                })
                if refund.success():
                    return {
                        "success": True,
                        "refund_id": refund.id,
                        "status": refund.state
                    }
                return {"success": False, "error": refund.error}
            else:
                return {"success": False, "error": "Unsupported payment provider"}
        except Exception as e:
            return {"success": False, "error": str(e)}
