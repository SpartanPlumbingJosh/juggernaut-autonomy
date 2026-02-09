"""
Stripe integration for payment processing and webhooks.
"""
import os
import stripe
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional

from core.database import query_db
from core.retry import exponential_backoff_retry

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

class StripePaymentError(Exception):
    """Custom exception for Stripe payment errors"""
    pass

@exponential_backoff_retry(max_retries=3, initial_delay=1)
async def create_checkout_session(
    price_id: str, 
    customer_email: str,
    success_url: str,
    cancel_url: str,
    metadata: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create a Stripe checkout session with retry logic.
    """
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='payment',
            customer_email=customer_email,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata or {}
        )
        return session
    except stripe.error.StripeError as e:
        raise StripePaymentError(f"Stripe API error: {str(e)}")

async def handle_stripe_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """
    Process Stripe webhook events with signature verification.
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except ValueError as e:
        raise StripePaymentError(f"Invalid payload: {str(e)}")
    except stripe.error.SignatureVerificationError as e:
        raise StripePaymentError(f"Invalid signature: {str(e)}")

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        await process_successful_payment(session)
    
    return {"status": "success"}

async def process_successful_payment(session: Dict[str, Any]) -> None:
    """
    Record successful payment and trigger service delivery.
    """
    try:
        payment_intent = stripe.PaymentIntent.retrieve(session['payment_intent'])
        
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {payment_intent['amount']},
                '{payment_intent['currency']}',
                'stripe',
                '{json.dumps({
                    'payment_intent': payment_intent['id'],
                    'customer_email': session.get('customer_email'),
                    **session.get('metadata', {})
                })}'::jsonb,
                NOW(),
                NOW()
            )
        """)
        
        # Trigger service delivery
        await deliver_service(session['id'], session.get('metadata', {}))
        
    except Exception as e:
        raise StripePaymentError(f"Failed to process payment: {str(e)}")

async def deliver_service(session_id: str, metadata: Dict[str, Any]) -> None:
    """
    Deliver the purchased service/product.
    """
    # Implementation depends on your specific service delivery logic
    # This could involve:
    # - Sending email with access credentials
    # - Generating and returning a license key  
    # - Starting a background processing job
    # - Updating user account status
    
    # Example implementation:
    service_type = metadata.get('service_type')
    user_email = metadata.get('user_email')
    
    if service_type and user_email:
        # Implement your service delivery logic here
        pass
