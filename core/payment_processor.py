import stripe
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

# Initialize Stripe with config
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

class PaymentProcessor:
    """Handle all payment operations including subscriptions and one-time payments."""
    
    DEFAULT_CURRENCY = 'usd'
    
    @classmethod
    def create_customer(cls, email: str, name: str = None, metadata: Dict = None) -> Dict:
        """Create a Stripe customer record."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {'success': True, 'customer_id': customer.id}
        except Exception as e:
            logging.error(f"Failed to create customer: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def create_subscription(cls, customer_id: str, price_id: str, metadata: Dict = None) -> Dict:
        """Create a recurring subscription."""
        try:
            sub = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                metadata=metadata or {},
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            return {
                'success': True,
                'subscription_id': sub.id,
                'client_secret': sub.latest_invoice.payment_intent.client_secret,
                'status': sub.status
            }
        except Exception as e:
            logging.error(f"Failed to create subscription: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def create_one_time_payment(cls, amount_cents: int, customer_id: str, description: str) -> Dict:
        """Process a single payment."""
        try:
            payment = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=cls.DEFAULT_CURRENCY,
                customer=customer_id,
                description=description,
                confirm=True,
                metadata={'type': 'one_time'}
            )
            return {'success': True, 'payment_id': payment.id, 'status': payment.status}
        except Exception as e:
            logging.error(f"Failed to create payment: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def handle_webhook_event(cls, payload: str, sig_header: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
            
            event_type = event['type']
            data = event['data']['object']
            
            if event_type == 'payment_intent.succeeded':
                # Handle successful payment
                metadata = data.get('metadata', {})
                return {'success': True, 'event': 'payment_success'}
                
            elif event_type == 'invoice.paid':
                # Handle subscription payment
                return {'success': True, 'event': 'invoice_paid'}
                
            return {'success': True, 'event': 'unhandled_event_type'} 
            
        except Exception as e:
            logging.error(f"Webhook processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}
