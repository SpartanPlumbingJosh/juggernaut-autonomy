import os
import stripe
import paypalrestsdk
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum

class PaymentGateway(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"

class PaymentGatewayService:
    def __init__(self):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        paypalrestsdk.configure({
            "mode": os.getenv("PAYPAL_MODE", "sandbox"),
            "client_id": os.getenv("PAYPAL_CLIENT_ID"),
            "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
        })

    async def create_customer(self, email: str, name: str, metadata: Dict) -> Dict:
        """Create customer in payment gateway"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata
            )
            return {
                "gateway": PaymentGateway.STRIPE.value,
                "customer_id": customer.id,
                "created": True
            }
        except Exception as e:
            return {"error": str(e)}

    async def create_subscription(self, customer_id: str, plan_id: str) -> Dict:
        """Create subscription for customer"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "payment_intent": subscription.latest_invoice.payment_intent
            }
        except Exception as e:
            return {"error": str(e)}

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict:
        """Process payment gateway webhook"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
            )
            
            if event.type == "invoice.payment_succeeded":
                return self._handle_payment_success(event.data.object)
            elif event.type == "invoice.payment_failed":
                return self._handle_payment_failure(event.data.object)
            elif event.type == "customer.subscription.deleted":
                return self._handle_subscription_cancelled(event.data.object)
            
            return {"status": "unhandled_event"}
        except Exception as e:
            return {"error": str(e)}

    def _handle_payment_success(self, invoice) -> Dict:
        """Handle successful payment"""
        return {
            "event": "payment_success",
            "invoice_id": invoice.id,
            "amount_paid": invoice.amount_paid,
            "customer_id": invoice.customer
        }

    def _handle_payment_failure(self, invoice) -> Dict:
        """Handle failed payment"""
        return {
            "event": "payment_failed",
            "invoice_id": invoice.id,
            "attempt_count": invoice.attempt_count,
            "customer_id": invoice.customer
        }

    def _handle_subscription_cancelled(self, subscription) -> Dict:
        """Handle subscription cancellation"""
        return {
            "event": "subscription_cancelled",
            "subscription_id": subscription.id,
            "customer_id": subscription.customer
        }
