"""
Billing Service - Handles payments, subscriptions, invoices and taxes.
Integrates with Stripe and PayPal APIs.
"""
import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List, Tuple

import stripe
import paypalrestsdk
from jinja2 import Environment, FileSystemLoader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize payment providers
stripe.api_key = os.getenv('STRIPE_API_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
})

class BillingService:
    def __init__(self):
        self.tax_rates = self._load_tax_rates()
        self.env = Environment(loader=FileSystemLoader('templates'))

    def _load_tax_rates(self) -> Dict[str, float]:
        """Load tax rates by country/region"""
        return {
            'US': 0.0,  # Varies by state
            'EU': 0.2,  # Standard VAT
            'UK': 0.2,  # VAT
            'CA': 0.05, # GST
            # Add more as needed
        }

    def calculate_tax(self, amount: float, country: str, state: Optional[str] = None) -> float:
        """Calculate tax based on location"""
        rate = self.tax_rates.get(country, 0.0)
        
        # US has state-level taxes
        if country == 'US' and state:
            state_rates = {
                'CA': 0.0725,
                'NY': 0.04,
                'TX': 0.0625,
            }
            rate = state_rates.get(state, 0.0)
            
        return round(amount * rate, 2)

    def create_stripe_customer(self, email: str, name: str, metadata: Dict = None) -> str:
        """Create a Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return customer.id
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation failed: {str(e)}")
            raise

    def create_payment_intent(self, amount: float, currency: str, customer_id: str, 
                            description: str, metadata: Dict = None) -> Dict:
        """Create a payment intent with Stripe"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                customer=customer_id,
                description=description,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True},
            )
            return {
                'client_secret': intent.client_secret,
                'payment_id': intent.id
            }
        except stripe.error.StripeError as e:
            logger.error(f"Payment intent creation failed: {str(e)}")
            raise

    def create_paypal_order(self, amount: float, currency: str, description: str) -> Dict:
        """Create a PayPal order"""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": str(amount),
                        "currency": currency.upper()
                    },
                    "description": description
                }],
                "redirect_urls": {
                    "return_url": os.getenv('PAYPAL_RETURN_URL'),
                    "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                }
            })
            
            if payment.create():
                return {
                    'approval_url': next(
                        link.href for link in payment.links 
                        if link.method == "REDIRECT" and link.rel == "approval_url"
                    ),
                    'payment_id': payment.id
                }
            raise Exception(payment.error)
        except Exception as e:
            logger.error(f"PayPal order creation failed: {str(e)}")
            raise

    def generate_invoice(self, payment_data: Dict, template_name: str = 'invoice.html') -> str:
        """Generate invoice HTML"""
        template = self.env.get_template(template_name)
        return template.render(**payment_data)

    def handle_webhook(self, payload: Dict, signature: str, provider: str) -> bool:
        """Process payment webhook from provider"""
        try:
            if provider == 'stripe':
                event = stripe.Webhook.construct_event(
                    payload, signature, os.getenv('STRIPE_WEBHOOK_SECRET')
                )
                return self._process_stripe_event(event)
            elif provider == 'paypal':
                # PayPal webhook verification
                return self._process_paypal_event(payload)
            return False
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return False

    def _process_stripe_event(self, event: Dict) -> bool:
        """Process Stripe webhook event"""
        event_type = event['type']
        
        if event_type == 'payment_intent.succeeded':
            payment = event['data']['object']
            # Record successful payment
            return True
            
        elif event_type == 'invoice.payment_failed':
            invoice = event['data']['object']
            # Handle failed payment (retry logic)
            return True
            
        elif event_type == 'customer.subscription.deleted':
            subscription = event['data']['object']
            # Handle subscription cancellation
            return True
            
        return False

    def _process_paypal_event(self, event: Dict) -> bool:
        """Process PayPal webhook event"""
        event_type = event.get('event_type')
        
        if event_type == 'PAYMENT.SALE.COMPLETED':
            # Record successful payment
            return True
            
        elif event_type == 'PAYMENT.SALE.DENIED':
            # Handle failed payment
            return True
            
        elif event_type == 'BILLING.SUBSCRIPTION.CANCELLED':
            # Handle subscription cancellation
            return True
            
        return False
