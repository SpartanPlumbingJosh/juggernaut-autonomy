"""
Payment Processor - Handles Stripe/PayPal integrations, subscriptions, and metering.
"""
import os
import stripe
import paypalrestsdk
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Configure payment providers
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_SECRET')
})

class PaymentProcessor:
    """Handles all payment processing operations."""
    
    @staticmethod
    async def create_customer(email: str, name: str, payment_method: str = 'stripe') -> Dict:
        """Create a new customer in payment system."""
        if payment_method == 'stripe':
            customer = stripe.Customer.create(email=email, name=name)
            return {'id': customer.id, 'payment_method': 'stripe'}
        else:
            customer = paypalrestsdk.Customer({
                "email": email,
                "name": name
            })
            if customer.create():
                return {'id': customer.id, 'payment_method': 'paypal'}
            raise Exception("Failed to create PayPal customer")

    @staticmethod
    async def create_subscription(
        customer_id: str,
        plan_id: str,
        payment_method: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create a new subscription."""
        metadata = metadata or {}
        if payment_method == 'stripe':
            sub = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': plan_id}],
                metadata=metadata
            )
            return {
                'id': sub.id,
                'status': sub.status,
                'current_period_end': sub.current_period_end
            }
        else:
            agreement = paypalrestsdk.BillingAgreement({
                "name": f"Subscription for {plan_id}",
                "description": "Recurring subscription",
                "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
                "plan": {"id": plan_id},
                "payer": {"payment_method": "paypal"},
                "shipping_address": metadata.get('shipping', {})
            })
            if agreement.create():
                return {
                    'id': agreement.id,
                    'status': agreement.state,
                    'approval_url': agreement.links[0].href
                }
            raise Exception("Failed to create PayPal subscription")

    @staticmethod
    async def record_usage(
        subscription_id: str,
        quantity: int,
        timestamp: int,
        action: str = 'increment'
    ) -> bool:
        """Record metered usage for a subscription."""
        try:
            stripe.SubscriptionItem.create_usage_record(
                subscription_id,
                quantity=quantity,
                timestamp=timestamp,
                action=action
            )
            return True
        except Exception as e:
            print(f"Failed to record usage: {str(e)}")
            return False

    @staticmethod
    async def generate_invoice(
        customer_id: str,
        items: List[Dict],
        payment_method: str
    ) -> Dict:
        """Generate an invoice for one-time charges."""
        if payment_method == 'stripe':
            invoice = stripe.Invoice.create(
                customer=customer_id,
                collection_method='charge_automatically',
                auto_advance=True,
                items=items
            )
            invoice = stripe.Invoice.finalize_invoice(invoice.id)
            return {
                'id': invoice.id,
                'amount_due': invoice.amount_due,
                'pdf_url': invoice.invoice_pdf,
                'status': invoice.status
            }
        else:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": str(sum(item['amount'] for item in items)),
                        "currency": "USD"
                    },
                    "description": "Service invoice"
                }],
                "redirect_urls": {
                    "return_url": os.getenv('PAYPAL_RETURN_URL'),
                    "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                }
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
            raise Exception("Failed to create PayPal invoice")

    @staticmethod
    async def handle_webhook(payload: Dict, sig_header: str, endpoint_secret: str) -> bool:
        """Process payment webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
            
            if event['type'] == 'invoice.payment_succeeded':
                # Record successful payment in revenue_events
                invoice = event['data']['object']
                await PaymentProcessor.record_revenue_event(
                    amount_cents=int(invoice['amount_paid'] * 100),
                    currency=invoice['currency'],
                    source='stripe',
                    metadata={
                        'invoice_id': invoice['id'],
                        'customer': invoice['customer'],
                        'subscription': invoice.get('subscription')
                    }
                )
            return True
        except Exception as e:
            print(f"Webhook processing failed: {str(e)}")
            return False

    @staticmethod
    async def record_revenue_event(
        amount_cents: int,
        currency: str,
        source: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Record a revenue event in the database."""
        # This would call your existing database layer
        # Implementation depends on your DB setup
        return True
