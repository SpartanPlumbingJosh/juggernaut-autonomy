import stripe
import paypalrestsdk
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from core.database import query_db

class PaymentProcessor:
    def __init__(self):
        self.stripe = stripe
        self.paypal = paypalrestsdk
        
    async def initialize(self, config: Dict[str, str]):
        """Initialize payment gateways with API keys"""
        self.stripe.api_key = config.get('stripe_secret_key')
        self.paypal.configure({
            'mode': config.get('paypal_mode', 'sandbox'),
            'client_id': config.get('paypal_client_id'),
            'client_secret': config.get('paypal_client_secret')
        })
        
    async def create_customer(self, email: str, payment_method: str, metadata: Dict[str, str]) -> Dict[str, Any]:
        """Create a customer in the payment gateway"""
        if payment_method == 'stripe':
            customer = self.stripe.Customer.create(
                email=email,
                metadata=metadata
            )
            return customer
        elif payment_method == 'paypal':
            # PayPal doesn't have direct customer objects
            return {'email': email, 'metadata': metadata}
        raise ValueError("Invalid payment method")

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: str) -> Dict[str, Any]:
        """Create a subscription for a customer"""
        if payment_method == 'stripe':
            subscription = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': plan_id}]
            )
            return subscription
        elif payment_method == 'paypal':
            agreement = self.paypal.BillingAgreement.create({
                'name': 'Subscription Agreement',
                'description': 'Recurring Payment',
                'start_date': (datetime.utcnow() + timedelta(days=1)).isoformat(),
                'plan': {
                    'id': plan_id
                },
                'payer': {
                    'payment_method': 'paypal'
                }
            })
            return agreement
        raise ValueError("Invalid payment method")

    async def handle_webhook(self, payload: Dict[str, Any], signature: str, payment_method: str) -> Dict[str, Any]:
        """Process webhook events from payment gateways"""
        if payment_method == 'stripe':
            event = self.stripe.Webhook.construct_event(
                payload, signature, self.stripe.webhook_secret
            )
            return self._process_stripe_event(event)
        elif payment_method == 'paypal':
            if self.paypal.notifications.webhook_event.verify(payload):
                return self._process_paypal_event(payload)
            raise ValueError("Invalid PayPal webhook signature")
        raise ValueError("Invalid payment method")

    def _process_stripe_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        event_type = event['type']
        data = event['data']['object']
        
        if event_type == 'payment_intent.succeeded':
            return self._record_payment(data)
        elif event_type == 'invoice.payment_failed':
            return self._handle_failed_payment(data)
        elif event_type == 'customer.subscription.deleted':
            return self._handle_subscription_cancellation(data)
        return {'status': 'unhandled_event'}

    def _process_paypal_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process PayPal webhook events"""
        event_type = event['event_type']
        resource = event['resource']
        
        if event_type == 'PAYMENT.SALE.COMPLETED':
            return self._record_payment(resource)
        elif event_type == 'BILLING.SUBSCRIPTION.CANCELLED':
            return self._handle_subscription_cancellation(resource)
        return {'status': 'unhandled_event'}

    async def _record_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record a successful payment"""
        # Insert into revenue_events table
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(float(payment_data['amount']) * 100)},
                '{payment_data['currency']}',
                'payment_processor',
                '{json.dumps(payment_data)}',
                NOW(),
                NOW()
            )
        """)
        return {'status': 'success'}

    async def _handle_failed_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment attempts"""
        # Notify customer and retry logic
        return {'status': 'failed_payment_handled'}

    async def _handle_subscription_cancellation(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription cancellations"""
        # Update subscription status
        return {'status': 'subscription_cancelled'}
