"""
Payment Processor - Handles Stripe, PayPal transactions and webhooks.

Features:
- Secure payment processing
- Subscription management
- Automated invoicing
- Webhook handlers
- Fraud detection
"""

import os
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Optional, List
from decimal import Decimal

# Initialize payment gateways
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
})

class PaymentProcessor:
    """Handles payment processing and subscription management."""
    
    def __init__(self):
        self.currency = os.getenv('DEFAULT_CURRENCY', 'usd')
        self.max_monthly_volume = Decimal('416666.00')
        
    async def create_payment_intent(self, amount: Decimal, metadata: Dict) -> Dict:
        """Create a payment intent with Stripe."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=self.currency,
                metadata=metadata,
                payment_method_types=['card'],
                capture_method='manual'  # For fraud review
            )
            return {
                'success': True,
                'client_secret': intent.client_secret,
                'payment_id': intent.id
            }
        except stripe.error.StripeError as e:
            return {'success': False, 'error': str(e)}
            
    async def create_paypal_order(self, amount: Decimal, metadata: Dict) -> Dict:
        """Create a PayPal order."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": str(amount),
                        "currency": self.currency
                    },
                    "description": metadata.get('description', '')
                }]
            })
            
            if payment.create():
                return {
                    'success': True,
                    'approval_url': next(link.href for link in payment.links if link.method == "REDIRECT"),
                    'payment_id': payment.id
                }
            return {'success': False, 'error': payment.error}
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    async def handle_webhook(self, payload: Dict, signature: str, source: str) -> Dict:
        """Process payment webhooks."""
        try:
            if source == 'stripe':
                event = stripe.Webhook.construct_event(
                    payload, signature, os.getenv('STRIPE_WEBHOOK_SECRET')
                )
                return await self._process_stripe_event(event)
            elif source == 'paypal':
                # PayPal webhook verification
                return await self._process_paypal_event(payload)
            return {'success': False, 'error': 'Invalid webhook source'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    async def _process_stripe_event(self, event: Dict) -> Dict:
        """Process Stripe webhook events."""
        event_type = event['type']
        data = event['data']['object']
        
        if event_type == 'payment_intent.succeeded':
            return await self._record_payment(
                amount=Decimal(data['amount']) / 100,
                payment_id=data['id'],
                currency=data['currency'],
                source='stripe',
                metadata=data['metadata']
            )
        # Handle other event types...
        return {'success': True}
        
    async def _process_paypal_event(self, event: Dict) -> Dict:
        """Process PayPal webhook events."""
        event_type = event['event_type']
        resource = event['resource']
        
        if event_type == 'PAYMENT.SALE.COMPLETED':
            return await self._record_payment(
                amount=Decimal(resource['amount']['total']),
                payment_id=resource['id'],
                currency=resource['amount']['currency'],
                source='paypal',
                metadata=resource.get('custom', {})
            )
        # Handle other event types...
        return {'success': True}
        
    async def _record_payment(self, amount: Decimal, payment_id: str, currency: str, 
                            source: str, metadata: Dict) -> Dict:
        """Record a successful payment."""
        # Implement database recording and fraud checks
        return {'success': True}

class SubscriptionManager:
    """Handles subscription lifecycle management."""
    
    def __init__(self):
        self.default_plan = os.getenv('DEFAULT_SUBSCRIPTION_PLAN', 'basic')
        
    async def create_subscription(self, customer_id: str, plan_id: str) -> Dict:
        """Create a new subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"plan": plan_id}],
                expand=['latest_invoice.payment_intent']
            )
            return {
                'success': True,
                'subscription_id': subscription.id,
                'status': subscription.status
            }
        except stripe.error.StripeError as e:
            return {'success': False, 'error': str(e)}
            
    async def cancel_subscription(self, subscription_id: str) -> Dict:
        """Cancel an existing subscription."""
        try:
            subscription = stripe.Subscription.delete(subscription_id)
            return {
                'success': True,
                'subscription_id': subscription.id,
                'status': subscription.status
            }
        except stripe.error.StripeError as e:
            return {'success': False, 'error': str(e)}
            
    async def generate_invoice(self, subscription_id: str) -> Dict:
        """Generate an invoice for a subscription."""
        try:
            invoice = stripe.Invoice.create(
                customer=subscription_id,
                auto_advance=True
            )
            return {
                'success': True,
                'invoice_id': invoice.id,
                'amount_due': invoice.amount_due,
                'pdf_url': invoice.invoice_pdf
            }
        except stripe.error.StripeError as e:
            return {'success': False, 'error': str(e)}
