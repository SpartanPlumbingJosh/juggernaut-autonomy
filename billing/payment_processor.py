"""
Payment processing system with Stripe/PayPal integrations.
Handles subscriptions, one-time payments, and invoicing.
"""

import os
import stripe
import paypalrestsdk
from typing import Dict, Optional, Union
from datetime import datetime

class PaymentProcessor:
    def __init__(self):
        self.stripe_api_key = os.getenv('STRIPE_API_KEY')
        self.paypal_client_id = os.getenv('PAYPAL_CLIENT_ID')
        self.paypal_secret = os.getenv('PAYPAL_SECRET')
        
        stripe.api_key = self.stripe_api_key
        paypalrestsdk.configure({
            "mode": "live" if os.getenv('PAYMENT_ENV') == 'production' else "sandbox",
            "client_id": self.paypal_client_id,
            "client_secret": self.paypal_secret
        })

    def create_customer(self, email: str, name: str, payment_method: str = 'stripe') -> Dict:
        """Create a new customer in payment system."""
        if payment_method == 'stripe':
            customer = stripe.Customer.create(
                email=email,
                name=name,
                description=f"Customer created on {datetime.now().isoformat()}"
            )
            return {'id': customer.id, 'source': 'stripe'}
        else:
            customer = paypalrestsdk.Customer({
                "email": email,
                "name": name
            })
            if customer.create():
                return {'id': customer.id, 'source': 'paypal'}
            raise Exception(f"PayPal customer creation failed: {customer.error}")

    def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        payment_source: str = 'stripe'
    ) -> Dict:
        """Create recurring subscription."""
        if payment_source == 'stripe':
            sub = stripe.Subscription.create(
                customer=customer_id,
                items=[{'plan': plan_id}]
            )
            return {
                'id': sub.id,
                'status': sub.status,
                'current_period_end': sub.current_period_end
            }
        else:
            agreement = paypalrestsdk.BillingAgreement({
                "name": "Subscription Agreement",
                "description": "Recurring payment agreement",
                "start_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "plan": {"id": plan_id},
                "payer": {"payment_method": "paypal"}
            })
            if agreement.create():
                return {
                    'id': agreement.id,
                    'status': agreement.state,
                    'approval_url': agreement.links[0].href
                }
            raise Exception(f"PayPal subscription failed: {agreement.error}")

    def process_payment(
        self,
        amount: float,
        currency: str,
        customer_id: Optional[str] = None,
        payment_method: str = 'stripe',
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Process one-time payment."""
        metadata = metadata or {}
        if payment_method == 'stripe':
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # cents
                currency=currency.lower(),
                customer=customer_id,
                metadata=metadata
            )
            return {
                'id': intent.id,
                'client_secret': intent.client_secret,
                'status': intent.status
            }
        else:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": str(amount),
                        "currency": currency.upper()
                    },
                    "description": metadata.get('description', '')
                }]
            })
            if payment.create():
                return {
                    'id': payment.id,
                    'approval_url': next(
                        link.href for link in payment.links 
                        if link.method == "REDIRECT"
                    ),
                    'status': payment.state
                }
            raise Exception(f"PayPal payment failed: {payment.error}")

    def create_invoice(
        self,
        customer_id: str,
        amount: float,
        currency: str,
        description: str,
        payment_source: str = 'stripe'
    ) -> Dict:
        """Create and send invoice to customer."""
        if payment_source == 'stripe':
            invoice = stripe.Invoice.create(
                customer=customer_id,
                amount=int(amount * 100),
                currency=currency.lower(),
                description=description,
                auto_advance=True
            )
            return {
                'id': invoice.id,
                'number': invoice.number,
                'status': invoice.status,
                'hosted_url': invoice.hosted_invoice_url
            }
        else:
            invoice = paypalrestsdk.Invoice({
                "merchant_info": {
                    "email": os.getenv('PAYPAL_MERCHANT_EMAIL')
                },
                "billing_info": [{"email": customer_id}],
                "items": [{
                    "name": description,
                    "quantity": 1,
                    "unit_price": {
                        "currency": currency.upper(),
                        "value": str(amount)
                    }
                }],
                "note": description,
                "payment_term": {
                    "term_type": "NET_45"
                }
            })
            if invoice.create() and invoice.send():
                return {
                    'id': invoice.id,
                    'number': invoice.number,
                    'status': invoice.status,
                    'view_url': invoice.metadata.get('payer_view_url')
                }
            raise Exception(f"PayPal invoice failed: {invoice.error}")

    def record_revenue_event(
        self,
        amount: float,
        currency: str,
        event_type: str,
        source: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Record revenue event in our system."""
        metadata = metadata or {}
        try:
            # This would call the database to record the transaction
            # For now we'll just return success
            return True
        except Exception as e:
            print(f"Failed to record revenue event: {str(e)}")
            return False
