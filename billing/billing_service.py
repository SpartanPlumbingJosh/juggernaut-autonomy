"""
Core billing service handling subscriptions, usage-based billing, invoicing and tax compliance.
Integrates with Stripe for payment processing and provides customer portal functionality.
"""

import os
import stripe
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
stripe.api_version = "2023-08-16"

class BillingService:
    def __init__(self):
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        
    async def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer": customer}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def create_subscription(self, customer_id: str, price_id: str, quantity: int = 1) -> Dict:
        """Create a new subscription"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{
                    'price': price_id,
                    'quantity': quantity
                }],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            return {"success": True, "subscription": subscription}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def record_usage(self, subscription_item_id: str, quantity: int, timestamp: Optional[int] = None) -> Dict:
        """Record usage for metered billing"""
        try:
            timestamp = timestamp or int(datetime.now(timezone.utc).timestamp())
            usage_record = stripe.SubscriptionItem.create_usage_record(
                subscription_item_id,
                quantity=quantity,
                timestamp=timestamp,
                action='increment'
            )
            return {"success": True, "usage_record": usage_record}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def create_invoice(self, customer_id: str, items: List[Dict], auto_advance: bool = True) -> Dict:
        """Create an invoice"""
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                auto_advance=auto_advance,
                collection_method='charge_automatically',
                items=items
            )
            return {"success": True, "invoice": invoice}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict:
        """Handle Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            # Handle specific event types
            if event['type'] == 'invoice.payment_succeeded':
                await self._handle_payment_succeeded(event)
            elif event['type'] == 'invoice.payment_failed':
                await self._handle_payment_failed(event)
            elif event['type'] == 'customer.subscription.updated':
                await self._handle_subscription_updated(event)
                
            return {"success": True}
        except stripe.error.SignatureVerificationError as e:
            return {"success": False, "error": "Invalid signature"}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def _handle_payment_succeeded(self, event: Dict) -> None:
        """Handle successful payment"""
        invoice = event['data']['object']
        # Update internal records, send notifications, etc.
        
    async def _handle_payment_failed(self, event: Dict) -> None:
        """Handle failed payment"""
        invoice = event['data']['object']
        # Notify customer, update internal records, etc.
        
    async def _handle_subscription_updated(self, event: Dict) -> None:
        """Handle subscription changes"""
        subscription = event['data']['object']
        # Update internal records, notify customer, etc.

    async def get_customer_portal_url(self, customer_id: str) -> Dict:
        """Generate customer portal URL"""
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url="https://your-app.com/dashboard"
            )
            return {"success": True, "url": session.url}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def calculate_tax(self, customer_id: str, amount: Decimal, currency: str) -> Dict:
        """Calculate tax for a given amount"""
        try:
            calculation = stripe.tax.Calculation.create(
                currency=currency,
                customer=customer_id,
                line_items=[{
                    'amount': int(amount * 100),
                    'reference': 'product'
                }]
            )
            return {
                "success": True,
                "tax_amount": Decimal(calculation['tax_amount_exclusive']) / 100,
                "total_amount": Decimal(calculation['amount_total']) / 100
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
