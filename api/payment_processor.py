"""
Payment Processor - Handles payment integrations and transaction processing.

Supports:
- Stripe
- PayPal
- Transaction validation
- Automated retries
- Audit logging
"""

import os
import time
import logging
from typing import Dict, Optional
from datetime import datetime, timezone

import stripe
import paypalrestsdk

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize payment gateways
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
})

class PaymentProcessor:
    """Handles payment processing with retry logic and validation."""
    
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    
    def __init__(self):
        self.payment_methods = {
            'stripe': self._process_stripe_payment,
            'paypal': self._process_paypal_payment
        }
    
    async def process_payment(self, payment_data: Dict) -> Dict:
        """
        Process payment with retry logic and validation.
        
        Args:
            payment_data: Dict containing payment details
                {
                    'amount': float,
                    'currency': str,
                    'payment_method': str,
                    'customer_email': str,
                    'description': str,
                    'metadata': Dict
                }
        
        Returns:
            Dict with payment status and details
        """
        # Validate input
        if not self._validate_payment_data(payment_data):
            return {'status': 'error', 'message': 'Invalid payment data'}
        
        # Try processing with retries
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                processor = self.payment_methods.get(payment_data['payment_method'])
                if not processor:
                    return {'status': 'error', 'message': 'Unsupported payment method'}
                
                result = await processor(payment_data)
                if result['status'] == 'success':
                    return result
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Payment attempt {attempt + 1} failed: {last_error}")
                time.sleep(self.RETRY_DELAY)
        
        logger.error(f"Payment failed after {self.MAX_RETRIES} attempts")
        return {'status': 'error', 'message': last_error or 'Payment failed'}
    
    def _validate_payment_data(self, payment_data: Dict) -> bool:
        """Validate payment data structure and values."""
        required_fields = ['amount', 'currency', 'payment_method', 'customer_email']
        return all(field in payment_data for field in required_fields)
    
    async def _process_stripe_payment(self, payment_data: Dict) -> Dict:
        """Process payment through Stripe."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(payment_data['amount'] * 100),  # Convert to cents
                currency=payment_data['currency'],
                description=payment_data.get('description', ''),
                metadata=payment_data.get('metadata', {}),
                receipt_email=payment_data['customer_email']
            )
            
            if intent.status == 'succeeded':
                return {
                    'status': 'success',
                    'transaction_id': intent.id,
                    'amount': payment_data['amount'],
                    'currency': payment_data['currency'],
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            return {'status': 'error', 'message': intent.last_payment_error or 'Payment failed'}
        
        except stripe.error.StripeError as e:
            return {'status': 'error', 'message': str(e)}
    
    async def _process_paypal_payment(self, payment_data: Dict) -> Dict:
        """Process payment through PayPal."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "transactions": [{
                    "amount": {
                        "total": str(payment_data['amount']),
                        "currency": payment_data['currency']
                    },
                    "description": payment_data.get('description', '')
                }],
                "redirect_urls": {
                    "return_url": os.getenv('PAYPAL_RETURN_URL'),
                    "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                }
            })
            
            if payment.create():
                return {
                    'status': 'success',
                    'transaction_id': payment.id,
                    'amount': payment_data['amount'],
                    'currency': payment_data['currency'],
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            return {'status': 'error', 'message': payment.error or 'Payment failed'}
        
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
