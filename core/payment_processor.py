import os
import stripe
from datetime import datetime, timezone
from typing import Dict, Any

from core.database import query_db

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

async def process_successful_payment(payment_intent: Dict[str, Any]) -> None:
    """Record successful payment in database."""
    try:
        amount = payment_intent['amount'] / 100  # Convert to dollars
        currency = payment_intent['currency']
        customer_id = payment_intent.get('customer')
        metadata = payment_intent.get('metadata', {})
        
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(amount * 100)},
                '{currency}',
                'stripe',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
            """
        )
        
        # Trigger any post-payment actions
        await handle_post_payment(payment_intent)

    except Exception as e:
        # Log error but don't fail webhook
        print(f"Failed to process payment: {str(e)}")

async def handle_post_payment(payment_intent: Dict[str, Any]) -> None:
    """Handle post-payment actions like onboarding."""
    metadata = payment_intent.get('metadata', {})
    if metadata.get('product_type') == 'subscription':
        # Handle subscription onboarding
        customer_id = payment_intent.get('customer')
        await onboard_customer(customer_id)

async def onboard_customer(customer_id: str) -> None:
    """Automated customer onboarding flow."""
    try:
        customer = stripe.Customer.retrieve(customer_id)
        # Implement your onboarding logic here
        # Example: Send welcome email, create user account, etc.
        print(f"Onboarding customer: {customer.email}")
    except Exception as e:
        print(f"Onboarding failed: {str(e)}")
