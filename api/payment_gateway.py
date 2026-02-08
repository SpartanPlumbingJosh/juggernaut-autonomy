"""
Payment Gateway Integration - Handle Stripe/PayPal payments and subscriptions.
"""

import os
import stripe
import json
from datetime import datetime
from typing import Dict, Any, Optional

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

async def create_payment_intent(amount: int, currency: str = 'usd', metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a Stripe PaymentIntent."""
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            metadata=metadata or {},
            automatic_payment_methods={'enabled': True},
        )
        return {
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id,
            'status': intent.status
        }
    except Exception as e:
        return {'error': str(e)}

async def handle_stripe_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """Process Stripe webhook events."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )
        
        # Handle different event types
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            await process_successful_payment(payment_intent)
        elif event['type'] == 'customer.subscription.created':
            subscription = event['data']['object']
            await process_new_subscription(subscription)
        elif event['type'] == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            await process_recurring_payment(invoice)
            
        return {'status': 'success'}
    except Exception as e:
        return {'error': str(e)}

async def process_successful_payment(payment_intent: Dict[str, Any]) -> None:
    """Handle successful one-time payment."""
    # Record revenue event
    await record_revenue_event(
        amount=payment_intent['amount'],
        currency=payment_intent['currency'],
        payment_intent_id=payment_intent['id'],
        event_type='payment',
        metadata=payment_intent['metadata']
    )

async def process_new_subscription(subscription: Dict[str, Any]) -> None:
    """Handle new subscription creation."""
    # Record subscription event
    await record_revenue_event(
        amount=subscription['plan']['amount'],
        currency=subscription['plan']['currency'],
        subscription_id=subscription['id'],
        event_type='subscription',
        metadata=subscription['metadata']
    )

async def process_recurring_payment(invoice: Dict[str, Any]) -> None:
    """Handle recurring subscription payment."""
    # Record revenue event
    await record_revenue_event(
        amount=invoice['amount_paid'],
        currency=invoice['currency'],
        invoice_id=invoice['id'],
        event_type='recurring_payment',
        metadata=invoice['metadata']
    )

async def record_revenue_event(
    amount: int,
    currency: str,
    event_type: str,
    metadata: Dict[str, Any],
    **kwargs
) -> None:
    """Record revenue event in database."""
    # Convert amount to cents
    amount_cents = amount
    
    # Insert into revenue_events table
    await query_db(f"""
        INSERT INTO revenue_events (
            event_type,
            amount_cents,
            currency,
            source,
            metadata,
            recorded_at
        ) VALUES (
            '{event_type}',
            {amount_cents},
            '{currency}',
            'stripe',
            '{json.dumps(metadata)}',
            NOW()
        )
    """)

__all__ = ['create_payment_intent', 'handle_stripe_webhook']
