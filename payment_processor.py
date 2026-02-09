import os
import stripe
import paddle
from typing import Dict, Optional, Tuple
from datetime import datetime

class PaymentProcessor:
    """Handles all payment processing with Stripe and Paddle."""
    
    def __init__(self):
        self.stripe_api_key = os.getenv('STRIPE_API_KEY')
        self.paddle_vendor_id = os.getenv('PADDLE_VENDOR_ID')
        self.paddle_auth_code = os.getenv('PADDLE_AUTH_CODE')
        
        stripe.api_key = self.stripe_api_key
        paddle.set_vendor_id(self.paddle_vendor_id)
        paddle.set_auth_code(self.paddle_auth_code)
    
    async def create_customer(self, email: str, name: str, payment_method: str) -> Tuple[Optional[str], Optional[str]]:
        """Create customer in payment provider."""
        try:
            if payment_method == 'stripe':
                customer = stripe.Customer.create(email=email, name=name)
                return customer.id, None
            elif payment_method == 'paddle':
                customer = paddle.Customer.create(email=email, name=name)
                return customer.id, None
            return None, "Invalid payment method"
        except Exception as e:
            return None, str(e)
    
    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: str) -> Tuple[Optional[str], Optional[str]]:
        """Create subscription for customer."""
        try:
            if payment_method == 'stripe':
                sub = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{'price': plan_id}],
                    payment_behavior='default_incomplete',
                    expand=['latest_invoice.payment_intent']
                )
                return sub.id, None
            elif payment_method == 'paddle':
                sub = paddle.Subscription.create(
                    customer_id=customer_id,
                    plan_id=plan_id
                )
                return sub.id, None
            return None, "Invalid payment method"
        except Exception as e:
            return None, str(e)
    
    async def record_payment_event(self, event_data: Dict) -> bool:
        """Record payment event in database."""
        # Implementation would record in revenue_events table
        return True

    async def handle_webhook(self, payload: Dict, signature: str, provider: str) -> bool:
        """Process webhook events from payment providers."""
        try:
            if provider == 'stripe':
                event = stripe.Webhook.construct_event(
                    payload, signature, os.getenv('STRIPE_WEBHOOK_SECRET')
                )
            elif provider == 'paddle':
                event = paddle.Webhook.verify(
                    payload, signature, os.getenv('PADDLE_WEBHOOK_SECRET')
                )
            else:
                return False
            
            # Process different event types
            if event['type'] == 'payment.succeeded':
                await self.record_payment_event(event['data'])
            elif event['type'] == 'invoice.paid':
                await self.record_payment_event(event['data'])
            elif event['type'] == 'subscription.created':
                pass  # Handle new subscription
            
            return True
        except Exception:
            return False
