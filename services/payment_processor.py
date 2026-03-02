import os
import stripe
import logging
from datetime import datetime
from typing import Dict, Optional

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Handles payment processing and service delivery automation"""
    
    def __init__(self):
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
    async def create_customer(self, email: str, name: str) -> Dict:
        """Create a new customer in Stripe"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={
                    'onboarded_at': datetime.utcnow().isoformat()
                }
            )
            return {'success': True, 'customer_id': customer.id}
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    async def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a subscription for a customer"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            return {
                'success': True,
                'subscription_id': subscription.id,
                'client_secret': subscription.latest_invoice.payment_intent.client_secret
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    async def handle_webhook(self, payload: str, sig_header: str) -> Dict:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                await self._handle_payment_success(event)
            elif event['type'] == 'payment_intent.payment_failed':
                await self._handle_payment_failure(event)
            elif event['type'] == 'invoice.payment_succeeded':
                await self._handle_subscription_payment(event)
                
            return {'success': True}
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    async def _handle_payment_success(self, event: Dict) -> None:
        """Handle successful one-time payments"""
        payment_intent = event['data']['object']
        # Trigger service delivery
        logger.info(f"Payment succeeded: {payment_intent['id']}")
        
    async def _handle_payment_failure(self, event: Dict) -> None:
        """Handle failed payments"""
        payment_intent = event['data']['object']
        logger.error(f"Payment failed: {payment_intent['id']}")
        # Trigger retry logic or notify customer
        
    async def _handle_subscription_payment(self, event: Dict) -> None:
        """Handle successful subscription payments"""
        invoice = event['data']['object']
        logger.info(f"Subscription payment succeeded: {invoice['id']}")
        # Trigger recurring service delivery
        
    async def monitor_transactions(self) -> Dict:
        """Check for failed transactions and trigger alerts"""
        try:
            failed_payments = stripe.PaymentIntent.list(
                status='failed',
                limit=10
            )
            
            if failed_payments.data:
                logger.warning(f"Found {len(failed_payments.data)} failed payments")
                # Trigger alerting system
                
            return {'success': True, 'failed_count': len(failed_payments.data)}
        except stripe.error.StripeError as e:
            logger.error(f"Failed to monitor transactions: {str(e)}")
            return {'success': False, 'error': str(e)}
