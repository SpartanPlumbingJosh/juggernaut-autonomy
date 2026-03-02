"""
Payment processing module with Stripe/Paddle integration.
Handles subscriptions, metered billing, invoices and dunning.
"""
import logging
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import stripe
import paddle

class PaymentProvider(Enum):
    STRIPE = 'stripe'
    PADDLE = 'paddle'

class PaymentService:
    def __init__(self, config: Dict[str, Any]):
        self.stripe_key = config.get('stripe_secret_key')
        self.paddle_key = config.get('paddle_auth_code')
        self.webhook_secret = config.get('webhook_secret')
        self.dry_run = config.get('dry_run', False)
        
        stripe.api_key = self.stripe_key
        paddle.set_api_key(self.paddle_key)
        
        self.logger = logging.getLogger(__name__)

    async def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create customer in both payment providers"""
        customers = {}
        
        if not self.dry_run and self.stripe_key:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            customers['stripe'] = customer.id
            
        if not self.dry_run and self.paddle_key:
            customer = paddle.Customer.create(
                email=email,
                name=name,
                custom_data=metadata or {}
            )
            customers['paddle'] = customer.id
            
        return customers
        
    async def create_subscription(self, customer_id: str, plan_id: str, provider: PaymentProvider) -> Dict:
        """Create subscription for customer"""
        if provider == PaymentProvider.STRIPE:
            sub = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': plan_id}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            return {
                'subscription_id': sub.id,
                'client_secret': sub.latest_invoice.payment_intent.client_secret,
                'status': sub.status
            }
        else:  # Paddle
            sub = paddle.Subscription.create(
                customer_id=customer_id,
                plan_id=plan_id
            )
            return {
                'subscription_id': sub.id,
                'checkout_url': sub.checkout_url,
                'status': 'active' if sub.success else 'failed'
            }
