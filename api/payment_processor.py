"""
Payment processing integration with Stripe and Paddle.
Handles subscriptions, one-time payments, and webhook events.
"""

import os
import uuid
import stripe
import paddle
from datetime import datetime, timezone
from typing import Dict, Optional, List

STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')
PADDLE_VENDOR_ID = os.getenv('PADDLE_VENDOR_ID')
PADDLE_API_KEY = os.getenv('PADDLE_API_KEY')

stripe.api_key = STRIPE_API_KEY
paddle.VENDOR_ID = int(PADDLE_VENDOR_ID) if PADDLE_VENDOR_ID else None
paddle.API_KEY = PADDLE_API_KEY

class PaymentProcessor:
    """Handle payment processing and revenue tracking."""

    @staticmethod
    def create_stripe_checkout(
        price_id: str, 
        customer_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create Stripe checkout session."""
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription' if 'subscription' in price_id else 'payment',
            customer=customer_id,
            metadata=metadata or {},
            success_url=f"{os.getenv('BASE_URL')}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{os.getenv('BASE_URL')}/payment/cancel",
        )
        return {
            'session_id': session.id,
            'checkout_url': session.url,
            'processor': 'stripe'
        }

    @staticmethod
    def create_paddle_checkout(
        product_id: str,
        customer_email: str,
        passthrough: Optional[Dict] = None
    ) -> Dict:
        """Create Paddle checkout URL."""
        checkout = paddle.Checkout.product(
            product_id=product_id,
            customer_email=customer_email,
            passthrough=passthrough or {},
            success_url=f"{os.getenv('BASE_URL')}/payment/success",
            cancel_url=f"{os.getenv('BASE_URL')}/payment/cancel"
        )
        return {
            'checkout_id': checkout.id,
            'checkout_url': checkout.url,
            'processor': 'paddle'
        }

    @staticmethod
    def log_revenue_event(
        execute_sql: callable,
        event_type: str,
        amount_cents: int,
        currency: str,
        idempotency_key: str,
        source: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Log revenue/cost event with idempotency protection."""
        try:
            # Check for existing event with same idempotency key
            check = execute_sql(
                f"""
                SELECT 1 FROM revenue_events 
                WHERE idempotency_key = '{idempotency_key}'
                LIMIT 1
                """
            )
            if check.get('rows'):
                return True  # Already logged
            
            execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, 
                    created_at, idempotency_key
                ) VALUES (
                    gen_random_uuid(),
                    '{event_type}',
                    {amount_cents},
                    '{currency}',
                    '{source}',
                    '{json.dumps(metadata) if metadata else '{}'}',
                    NOW(),
                    NOW(),
                    '{idempotency_key}'
                )
                """
            )
            return True
        except Exception as e:
            print(f"Failed to log revenue event: {str(e)}")
            return False

    @staticmethod
    def handle_webhook(event: Dict, processor: str) -> bool:
        """Process payment webhook events."""
        idempotency_key = f"{processor}:{event.get('id', str(uuid.uuid4()))}"
        event_type = event.get('type')
        
        if processor == 'stripe':
            if event_type == 'payment_intent.succeeded':
                payment = event['data']['object']
                amount = payment['amount']
                currency = payment['currency']
                return PaymentProcessor.log_revenue_event(
                    execute_sql,
                    'revenue',
                    amount,
                    currency,
                    idempotency_key,
                    'stripe',
                    payment
                )
        
        elif processor == 'paddle':
            if event_type == 'subscription_payment_succeeded':
                payload = event['data']['payload']
                amount = payload['sale_gross'] * 100  # Convert to cents
                currency = payload['currency']
                return PaymentProcessor.log_revenue_event(
                    execute_sql,
                    'revenue',
                    amount,
                    currency,
                    idempotency_key,
                    'paddle',
                    payload
                )
        
        return False


__all__ = ['PaymentProcessor']
