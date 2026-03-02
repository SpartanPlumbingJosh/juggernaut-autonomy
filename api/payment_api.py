"""
Payment Processing API - Handles Stripe/Paddle integrations, subscriptions, and webhooks.
"""
import os
import stripe
import json
from datetime import datetime
from typing import Any, Dict, Optional

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

async def create_customer(email: str, name: str) -> Dict[str, Any]:
    """Create a new customer in Stripe."""
    try:
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={
                'created_at': datetime.utcnow().isoformat()
            }
        )
        return {
            'success': True,
            'customer_id': customer.id,
            'email': customer.email
        }
    except stripe.error.StripeError as e:
        return {
            'success': False,
            'error': str(e)
        }

async def create_subscription(customer_id: str, price_id: str) -> Dict[str, Any]:
    """Create a new subscription for a customer."""
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
            'client_secret': subscription.latest_invoice.payment_intent.client_secret,
            'status': subscription.status
        }
    except stripe.error.StripeError as e:
        return {
            'success': False,
            'error': str(e)
        }

async def handle_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process Stripe webhook events."""
    event_type = event['type']
    data = event['data']
    
    if event_type == 'customer.subscription.created':
        # Handle new subscription
        subscription = data['object']
        customer_id = subscription['customer']
        # Update user's subscription status in database
        return {'success': True, 'message': 'Subscription created'}
    
    elif event_type == 'invoice.payment_succeeded':
        # Handle successful payment
        invoice = data['object']
        customer_id = invoice['customer']
        amount_paid = invoice['amount_paid']
        # Update billing records
        return {'success': True, 'message': 'Payment succeeded'}
    
    return {'success': False, 'error': 'Unhandled event type'}

__all__ = ['create_customer', 'create_subscription', 'handle_webhook']
