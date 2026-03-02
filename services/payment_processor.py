"""
Payment processing service with Stripe integration.
Handles subscriptions, one-time payments, invoices.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import stripe

class PaymentProcessor:
    def __init__(self, api_key: str):
        self.stripe = stripe
        self.stripe.api_key = api_key

    async def create_customer(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new Stripe customer."""
        try:
            customer = self.stripe.Customer.create(
                email=user_data.get('email'),
                name=user_data.get('name'),
                metadata={
                    'user_id': user_data['user_id'],
                    'signup_date': datetime.utcnow().isoformat()
                }
            )
            return {
                'success': True,
                'customer_id': customer.id,
                'status': 'created'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)[:200]
            }

    async def create_subscription(self, customer_id: str, plan_id: str) -> Dict[str, Any]:
        """Create subscription for a customer."""
        try:
            subscription = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': plan_id}],
                expand=['latest_invoice.payment_intent']
            )
            return {
                'success': True,
                'subscription_id': subscription.id,
                'status': subscription.status,
                'payment_intent': (
                    subscription.latest_invoice.payment_intent
                    if subscription.latest_invoice
                    else None
                )
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)[:200]
            }

    async def process_one_time_payment(
        self,
        customer_id: str,
        amount: int,
        currency: str,
        description: str
    ) -> Dict[str, Any]:
        """Process single payment."""
        try:
            payment_intent = self.stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                description=description,
                automatic_payment_methods={
                    'enabled': True
                }
            )
            return {
                'success': True,
                'payment_intent_id': payment_intent.id,
                'client_secret': payment_intent.client_secret
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)[:200]
            }

    async def send_invoice(self, customer_id: str, items: list) -> Dict[str, Any]:
        """Generate and send invoice."""
        try:
            invoice = self.stripe.Invoice.create(
                customer=customer_id,
                collection_method='send_invoice',
                days_until_due=30,
                auto_advance=True
            )
            
            for item in items:
                self.stripe.InvoiceItem.create(
                    customer=customer_id,
                    price=item['price_id'],
                    quantity=item['quantity'],
                    invoice=invoice.id
                )
            
            invoice.send_invoice()
            return {
                'success': True,
                'invoice_id': invoice.id,
                'status': 'sent'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)[:200]
            }
