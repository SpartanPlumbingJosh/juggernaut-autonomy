import stripe
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    def create_customer(self, email: str, payment_method: str) -> Dict:
        """Create a new customer in Stripe"""
        customer = stripe.Customer.create(
            email=email,
            payment_method=payment_method,
            invoice_settings={
                'default_payment_method': payment_method
            }
        )
        return customer
    
    def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a subscription for a customer"""
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{'price': price_id}],
            expand=['latest_invoice.payment_intent']
        )
        return subscription
    
    def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Optional[Dict]:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                return self._handle_payment_success(event)
            elif event['type'] == 'invoice.payment_failed':
                return self._handle_payment_failure(event)
            elif event['type'] == 'customer.subscription.deleted':
                return self._handle_subscription_cancelled(event)
                
        except Exception as e:
            return {'error': str(e)}
        return None
    
    def _handle_payment_success(self, event: Dict) -> Dict:
        """Handle successful payment"""
        payment_intent = event['data']['object']
        return {
            'status': 'success',
            'customer_id': payment_intent['customer'],
            'amount': payment_intent['amount_received'],
            'currency': payment_intent['currency'],
            'timestamp': datetime.utcfromtimestamp(payment_intent['created'])
        }
    
    def _handle_payment_failure(self, event: Dict) -> Dict:
        """Handle failed payment"""
        invoice = event['data']['object']
        return {
            'status': 'failed',
            'customer_id': invoice['customer'],
            'attempt_count': invoice['attempt_count'],
            'next_payment_attempt': datetime.utcfromtimestamp(invoice['next_payment_attempt'])
        }
    
    def _handle_subscription_cancelled(self, event: Dict) -> Dict:
        """Handle subscription cancellation"""
        subscription = event['data']['object']
        return {
            'status': 'cancelled',
            'customer_id': subscription['customer'],
            'cancel_at': datetime.utcfromtimestamp(subscription['cancel_at']) if subscription['cancel_at'] else None
        }
