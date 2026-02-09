"""
Payment Service - Handles all payment processing logic including:
- Payment gateway integration (Stripe/PayPal)
- Subscription management
- Usage-based billing
- Invoicing
- Dunning management
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import stripe
import paypalrestsdk

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize payment gateways
stripe.api_key = os.getenv('STRIPE_API_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
})

class PaymentService:
    """Core payment processing service."""
    
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql
        self.fraud_rules = self._load_fraud_rules()
    
    def _load_fraud_rules(self) -> Dict:
        """Load fraud detection rules from database."""
        try:
            result = self.execute_sql("SELECT rules FROM fraud_detection_rules")
            return result.get('rows', [{}])[0].get('rules', {})
        except Exception:
            return {
                'max_amount': 100000,  # $1000
                'velocity_check': 5,   # max 5 payments/hour
                'country_blacklist': [],
                'ip_blacklist': []
            }
    
    def create_customer(self, email: str, name: str, metadata: Dict = None) -> Dict:
        """Create customer in all payment systems."""
        try:
            # Create Stripe customer
            stripe_customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            
            # Create PayPal customer
            paypal_customer = paypalrestsdk.Customer({
                "email": email,
                "name": name,
                "metadata": metadata or {}
            })
            if paypal_customer.create():
                return {
                    'success': True,
                    'stripe_id': stripe_customer.id,
                    'paypal_id': paypal_customer.id
                }
            return {'success': False, 'error': 'Failed to create PayPal customer'}
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def create_subscription(self, customer_id: str, plan_id: str, payment_method: str = 'stripe') -> Dict:
        """Create a new subscription."""
        try:
            if payment_method == 'stripe':
                sub = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{'plan': plan_id}],
                    expand=['latest_invoice.payment_intent']
                )
                return {
                    'success': True,
                    'subscription_id': sub.id,
                    'status': sub.status,
                    'current_period_end': sub.current_period_end
                }
            else:
                # PayPal subscription logic
                pass
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def process_payment(self, amount: int, currency: str, customer_id: str, 
                       source: str, description: str, metadata: Dict = None) -> Dict:
        """Process a payment."""
        try:
            # Fraud checks
            fraud_check = self._check_fraud(amount, currency, metadata)
            if not fraud_check['success']:
                return fraud_check
            
            # Process payment
            charge = stripe.Charge.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                source=source,
                description=description,
                metadata=metadata or {}
            )
            
            # Record transaction
            self._record_transaction(
                amount=amount,
                currency=currency,
                customer_id=customer_id,
                transaction_id=charge.id,
                status='succeeded',
                payment_method='stripe'
            )
            
            return {
                'success': True,
                'transaction_id': charge.id,
                'receipt_url': charge.receipt_url
            }
        except Exception as e:
            logger.error(f"Payment failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _check_fraud(self, amount: int, currency: str, metadata: Dict) -> Dict:
        """Run fraud detection checks."""
        try:
            # Amount check
            if amount > self.fraud_rules.get('max_amount', 100000):
                return {'success': False, 'error': 'Amount exceeds maximum limit'}
            
            # Velocity check
            recent_txns = self.execute_sql(
                f"SELECT COUNT(*) as count FROM payments "
                f"WHERE customer_id = '{metadata.get('customer_id')}' "
                f"AND created_at > NOW() - INTERVAL '1 hour'"
            )
            if recent_txns.get('rows', [{}])[0].get('count', 0) > self.fraud_rules.get('velocity_check', 5):
                return {'success': False, 'error': 'Too many recent transactions'}
            
            return {'success': True}
        except Exception as e:
            logger.error(f"Fraud check failed: {str(e)}")
            return {'success': False, 'error': 'Fraud check failed'}
    
    def _record_transaction(self, amount: int, currency: str, customer_id: str,
                          transaction_id: str, status: str, payment_method: str) -> None:
        """Record payment transaction in database."""
        try:
            self.execute_sql(
                f"INSERT INTO payments ("
                f"id, customer_id, amount, currency, transaction_id, "
                f"status, payment_method, created_at"
                f") VALUES ("
                f"gen_random_uuid(), '{customer_id}', {amount}, '{currency}', "
                f"'{transaction_id}', '{status}', '{payment_method}', NOW()"
                f")"
            )
        except Exception as e:
            logger.error(f"Failed to record transaction: {str(e)}")

    def handle_webhook(self, payload: Dict, signature: str, source: str) -> Dict:
        """Process payment webhook events."""
        try:
            if source == 'stripe':
                event = stripe.Webhook.construct_event(
                    payload, signature, os.getenv('STRIPE_WEBHOOK_SECRET')
                )
                
                if event.type == 'payment_intent.succeeded':
                    return self._handle_payment_success(event.data.object)
                elif event.type == 'payment_intent.payment_failed':
                    return self._handle_payment_failure(event.data.object)
                elif event.type == 'invoice.payment_failed':
                    return self._handle_invoice_failure(event.data.object)
            
            return {'success': False, 'error': 'Unhandled webhook event'}
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_payment_success(self, payment_intent: Dict) -> Dict:
        """Handle successful payment."""
        # Send receipt, update records, etc.
        return {'success': True}
    
    def _handle_payment_failure(self, payment_intent: Dict) -> Dict:
        """Handle failed payment."""
        # Retry logic, notify customer, etc.
        return {'success': True}
    
    def _handle_invoice_failure(self, invoice: Dict) -> Dict:
        """Handle failed invoice payment."""
        # Dunning management, retry logic, etc.
        return {'success': True}
