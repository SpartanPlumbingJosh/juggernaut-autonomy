import os
import stripe
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

class BillingManager:
    """Handles subscription management, invoicing, and payment processing."""
    
    def __init__(self):
        self.tax_rates = self._load_tax_rates()
    
    def _load_tax_rates(self) -> Dict[str, Any]:
        """Load tax rates from Stripe or local config"""
        try:
            rates = stripe.TaxRate.list(limit=100)
            return {r['id']: r for r in rates['data']}
        except Exception:
            return {}
    
    def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a new Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer": customer}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_subscription(self, customer_id: str, price_id: str, tax_rate_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new subscription"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                default_tax_rates=[tax_rate_id] if tax_rate_id else [],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            return {"success": True, "subscription": subscription}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
            
            # Handle specific event types
            if event['type'] == 'invoice.payment_succeeded':
                return self._handle_payment_success(event)
            elif event['type'] == 'invoice.payment_failed':
                return self._handle_payment_failure(event)
            elif event['type'] == 'customer.subscription.deleted':
                return self._handle_subscription_cancelled(event)
            
            return {"success": True, "handled": False}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_payment_success(self, event: Any) -> Dict[str, Any]:
        """Process successful payment"""
        invoice = event['data']['object']
        # Record revenue event
        return {"success": True, "handled": True}
    
    def _handle_payment_failure(self, event: Any) -> Dict[str, Any]:
        """Process failed payment"""
        invoice = event['data']['object']
        # Implement retry logic
        return {"success": True, "handled": True}
    
    def _handle_subscription_cancelled(self, event: Any) -> Dict[str, Any]:
        """Process subscription cancellation"""
        subscription = event['data']['object']
        # Update subscription status
        return {"success": True, "handled": True}
