"""
Automated billing management with Stripe/PayPal integration.

Features:
- Subscription management
- Payment processing
- Invoice generation
- Payment failure handling
"""

import os
import stripe
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List

class BillingManager:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new billing customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a new subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return {"success": True, "subscription_id": subscription.id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_webhook(self, payload: str, sig_header: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            # Handle specific event types
            if event['type'] == 'invoice.payment_succeeded':
                return self._handle_payment_success(event)
            elif event['type'] == 'invoice.payment_failed':
                return self._handle_payment_failure(event)
            elif event['type'] == 'customer.subscription.deleted':
                return self._handle_subscription_cancelled(event)
            
            return {"success": True, "event": event['type']}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_payment_success(self, event: Dict) -> Dict:
        """Handle successful payment."""
        invoice = event['data']['object']
        customer_id = invoice['customer']
        amount_paid = invoice['amount_paid'] / 100
        
        # Record revenue event
        return {
            "success": True,
            "customer_id": customer_id,
            "amount": amount_paid,
            "event": "payment_success"
        }

    def _handle_payment_failure(self, event: Dict) -> Dict:
        """Handle failed payment."""
        invoice = event['data']['object']
        customer_id = invoice['customer']
        
        # Trigger dunning process
        return {
            "success": True,
            "customer_id": customer_id,
            "event": "payment_failed"
        }

    def _handle_subscription_cancelled(self, event: Dict) -> Dict:
        """Handle subscription cancellation."""
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        # Trigger retention flow
        return {
            "success": True,
            "customer_id": customer_id,
            "event": "subscription_cancelled"
        }

    def generate_invoice(self, customer_id: str, amount: float, description: str) -> Dict:
        """Generate an invoice."""
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                amount=int(amount * 100),
                currency="usd",
                description=description,
                auto_advance=True
            )
            return {"success": True, "invoice_id": invoice.id}
        except Exception as e:
            return {"success": False, "error": str(e)}
