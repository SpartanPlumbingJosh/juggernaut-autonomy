import os
import stripe
import paypalrestsdk
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from cryptography.fernet import Fernet

# Initialize payment gateways with encrypted credentials
def _init_gateways():
    """Initialize payment gateways with encrypted credentials."""
    # Get encryption key from environment
    key = os.getenv('PAYMENT_ENCRYPTION_KEY')
    if not key:
        raise ValueError("Missing PAYMENT_ENCRYPTION_KEY in environment")
    
    cipher = Fernet(key.encode())
    
    # Decrypt and initialize Stripe
    stripe.api_key = cipher.decrypt(os.getenv('STRIPE_SECRET_KEY').encode()).decode()
    
    # Decrypt and initialize PayPal
    paypalrestsdk.configure({
        "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
        "client_id": cipher.decrypt(os.getenv('PAYPAL_CLIENT_ID').encode()).decode(),
        "client_secret": cipher.decrypt(os.getenv('PAYPAL_CLIENT_SECRET').encode()).decode()
    })

class PaymentProcessor:
    """Handle payment processing across multiple gateways."""
    
    def __init__(self):
        _init_gateways()
    
    def create_subscription(self, customer_id: str, plan_id: str, payment_method: str) -> Dict[str, Any]:
        """Create a new subscription."""
        if payment_method == 'stripe':
            return self._create_stripe_subscription(customer_id, plan_id)
        elif payment_method == 'paypal':
            return self._create_paypal_subscription(customer_id, plan_id)
        else:
            raise ValueError("Unsupported payment method")
    
    def _create_stripe_subscription(self, customer_id: str, plan_id: str) -> Dict[str, Any]:
        """Create Stripe subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': plan_id}],
                expand=['latest_invoice.payment_intent']
            )
            return {
                'status': 'success',
                'subscription_id': subscription.id,
                'payment_status': subscription.latest_invoice.payment_intent.status
            }
        except stripe.error.StripeError as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _create_paypal_subscription(self, customer_id: str, plan_id: str) -> Dict[str, Any]:
        """Create PayPal subscription."""
        try:
            agreement = paypalrestsdk.BillingAgreement({
                "name": "Subscription Agreement",
                "description": "Recurring payment agreement",
                "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z",
                "plan": {
                    "id": plan_id
                },
                "payer": {
                    "payment_method": "paypal"
                }
            })
            
            if agreement.create():
                return {
                    'status': 'success',
                    'subscription_id': agreement.id,
                    'payment_status': 'active'
                }
            else:
                return {
                    'status': 'failed',
                    'error': agreement.error
                }
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def handle_webhook(self, payload: Dict[str, Any], signature: str, source: str) -> bool:
        """Process payment webhook events."""
        if source == 'stripe':
            return self._handle_stripe_webhook(payload, signature)
        elif source == 'paypal':
            return self._handle_paypal_webhook(payload)
        else:
            raise ValueError("Unsupported webhook source")
    
    def _handle_stripe_webhook(self, payload: Dict[str, Any], signature: str) -> bool:
        """Process Stripe webhook."""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, os.getenv('STRIPE_WEBHOOK_SECRET')
            )
            
            if event['type'] == 'invoice.payment_failed':
                self._handle_failed_payment(event['data']['object'])
            elif event['type'] == 'invoice.payment_succeeded':
                self._handle_successful_payment(event['data']['object'])
            
            return True
        except Exception as e:
            return False
    
    def _handle_paypal_webhook(self, payload: Dict[str, Any]) -> bool:
        """Process PayPal webhook."""
        try:
            if payload['event_type'] == 'PAYMENT.SALE.COMPLETED':
                self._handle_successful_payment(payload)
            elif payload['event_type'] == 'PAYMENT.SALE.DENIED':
                self._handle_failed_payment(payload)
            return True
        except Exception as e:
            return False
    
    def _handle_successful_payment(self, payment_data: Dict[str, Any]) -> None:
        """Handle successful payment."""
        # Record revenue event and update subscription status
        pass
    
    def _handle_failed_payment(self, payment_data: Dict[str, Any]) -> None:
        """Handle failed payment."""
        # Update subscription status and trigger dunning process
        pass
