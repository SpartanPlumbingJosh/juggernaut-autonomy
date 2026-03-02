"""
Core payment processing infrastructure supporting Stripe and PayPal integrations.
Handles subscriptions, one-time payments, and metered billing.
"""

import os
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Optional, List, Tuple
from decimal import Decimal

class PaymentProcessor:
    def __init__(self):
        self.stripe_api_key = os.getenv("STRIPE_API_KEY")
        self.paypal_client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.paypal_secret = os.getenv("PAYPAL_SECRET")
        
        stripe.api_key = self.stripe_api_key
        paypalrestsdk.configure({
            "mode": "live" if os.getenv("PAYMENT_ENV") == "production" else "sandbox",
            "client_id": self.paypal_client_id,
            "client_secret": self.paypal_secret
        })

    async def create_customer(self, email: str, payment_method: str, metadata: Optional[Dict] = None) -> Tuple[str, str]:
        """Create customer in payment system"""
        if payment_method == "stripe":
            customer = stripe.Customer.create(
                email=email,
                metadata=metadata or {}
            )
            return customer.id, "stripe"
        elif payment_method == "paypal":
            # PayPal doesn't have a direct customer object, we'll use email as identifier
            return email, "paypal"
        raise ValueError("Invalid payment method")

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: str) -> Dict:
        """Create subscription for customer"""
        if payment_method == "stripe":
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "payment_intent": subscription.latest_invoice.payment_intent
            }
        elif payment_method == "paypal":
            # PayPal subscription creation logic
            pass
        raise ValueError("Invalid payment method")

    async def create_metered_usage_record(self, subscription_id: str, quantity: int, timestamp: datetime) -> Dict:
        """Record usage for metered billing"""
        timestamp_unix = int(timestamp.timestamp())
        usage_record = stripe.SubscriptionItem.create_usage_record(
            subscription_id,
            quantity=quantity,
            timestamp=timestamp_unix
        )
        return {
            "id": usage_record.id,
            "quantity": usage_record.quantity,
            "timestamp": usage_record.timestamp
        }

    async def handle_webhook(self, payload: bytes, signature: str, payment_method: str) -> Dict:
        """Process webhook events from payment providers"""
        if payment_method == "stripe":
            event = stripe.Webhook.construct_event(
                payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET")
            )
            return self._process_stripe_event(event)
        elif payment_method == "paypal":
            # PayPal webhook processing
            pass
        raise ValueError("Invalid payment method")

    def _process_stripe_event(self, event: stripe.Event) -> Dict:
        """Process Stripe webhook event"""
        event_type = event['type']
        data = event['data']
        
        if event_type == "invoice.payment_succeeded":
            return self._handle_payment_success(data)
        elif event_type == "invoice.payment_failed":
            return self._handle_payment_failure(data)
        elif event_type == "customer.subscription.deleted":
            return self._handle_subscription_cancelled(data)
        
        return {"status": "unhandled_event", "event_type": event_type}

    def _handle_payment_success(self, data: Dict) -> Dict:
        """Handle successful payment"""
        invoice = data['object']
        return {
            "status": "payment_success",
            "amount_paid": invoice['amount_paid'],
            "currency": invoice['currency'],
            "customer_id": invoice['customer']
        }

    def _handle_payment_failure(self, data: Dict) -> Dict:
        """Handle failed payment"""
        invoice = data['object']
        return {
            "status": "payment_failed",
            "attempt_count": invoice['attempt_count'],
            "next_payment_attempt": invoice['next_payment_attempt'],
            "customer_id": invoice['customer']
        }

    def _handle_subscription_cancelled(self, data: Dict) -> Dict:
        """Handle subscription cancellation"""
        subscription = data['object']
        return {
            "status": "subscription_cancelled",
            "customer_id": subscription['customer'],
            "cancel_at_period_end": subscription['cancel_at_period_end']
        }

    async def get_payment_history(self, customer_id: str, payment_method: str) -> List[Dict]:
        """Get payment history for customer"""
        if payment_method == "stripe":
            charges = stripe.Charge.list(customer=customer_id)
            return [{
                "id": charge.id,
                "amount": charge.amount,
                "currency": charge.currency,
                "created": charge.created,
                "status": charge.status
            } for charge in charges.auto_paging_iter()]
        elif payment_method == "paypal":
            # PayPal payment history retrieval
            pass
        raise ValueError("Invalid payment method")

    async def refund_payment(self, payment_id: str, payment_method: str, amount: Optional[Decimal] = None) -> Dict:
        """Process refund for payment"""
        if payment_method == "stripe":
            refund = stripe.Refund.create(
                charge=payment_id,
                amount=int(amount * 100) if amount else None
            )
            return {
                "id": refund.id,
                "status": refund.status,
                "amount": refund.amount
            }
        elif payment_method == "paypal":
            # PayPal refund processing
            pass
        raise ValueError("Invalid payment method")
