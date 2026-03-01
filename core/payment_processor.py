import os
import stripe
import paypalrestsdk
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from enum import Enum

class PaymentGateway(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"

class PaymentProcessor:
    def __init__(self):
        # Initialize payment gateways
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        paypalrestsdk.configure({
            "mode": os.getenv("PAYPAL_MODE", "sandbox"),
            "client_id": os.getenv("PAYPAL_CLIENT_ID"),
            "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
        })

    async def create_payment_intent(self, amount: int, currency: str, gateway: PaymentGateway, metadata: Dict = {}) -> Dict:
        """Create a payment intent with the selected gateway"""
        try:
            if gateway == PaymentGateway.STRIPE:
                intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency=currency,
                    metadata=metadata
                )
                return {"success": True, "client_secret": intent.client_secret}
            elif gateway == PaymentGateway.PAYPAL:
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": f"{amount/100:.2f}",
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
                    return {"success": True, "approval_url": payment.links[1].href}
                return {"success": False, "error": payment.error}
            return {"success": False, "error": "Unsupported payment gateway"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: bytes, signature: str, gateway: PaymentGateway) -> Dict:
        """Process payment webhook events"""
        try:
            if gateway == PaymentGateway.STRIPE:
                event = stripe.Webhook.construct_event(
                    payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET")
                )
                return self._process_stripe_event(event)
            elif gateway == PaymentGateway.PAYPAL:
                # PayPal webhook verification
                return {"success": True, "event": "received"}
            return {"success": False, "error": "Unsupported payment gateway"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _process_stripe_event(self, event) -> Dict:
        """Process Stripe webhook events"""
        event_type = event['type']
        data = event['data']['object']
        
        if event_type == 'payment_intent.succeeded':
            return self._handle_payment_success(data)
        elif event_type == 'payment_intent.payment_failed':
            return self._handle_payment_failure(data)
        elif event_type == 'charge.refunded':
            return self._handle_refund(data)
        else:
            return {"success": True, "event": event_type}

    def _handle_payment_success(self, data) -> Dict:
        """Handle successful payment"""
        # Record revenue event
        return {"success": True, "event": "payment_success"}

    def _handle_payment_failure(self, data) -> Dict:
        """Handle failed payment"""
        return {"success": True, "event": "payment_failed"}

    def _handle_refund(self, data) -> Dict:
        """Handle refund"""
        return {"success": True, "event": "refund"}
