"""
Billing Service - Handles payment processing and invoice management.
"""
import uuid
import stripe
from datetime import datetime, timezone
from typing import Dict, Optional

from config import settings
from core.database import query_db

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

async def create_payment_intent(amount_cents: int, customer_id: str) -> Dict:
    """Create a Stripe PaymentIntent."""
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='usd',
            customer=customer_id,
            automatic_payment_methods={
                'enabled': True,
            },
            metadata={
                'system': 'spartan',
                'environment': settings.ENVIRONMENT
            }
        )
        return {
            'client_secret': intent.client_secret,
            'amount': intent.amount,
            'status': intent.status,
            'payment_intent_id': intent.id
        }
    except stripe.error.StripeError as e:
        return {'error': str(e)}

async def record_transaction(
    payment_intent_id: str,
    amount_cents: int,
    customer_id: str,
    service_id: str,
    metadata: Optional[Dict] = None
) -> Dict:
    """Record a successful transaction in our database."""
    try:
        transaction_id = str(uuid.uuid4())
        
        await query_db(f"""
            INSERT INTO revenue_events (
                id, 
                experiment_id,
                event_type,
                amount_cents,
                currency,
                source,
                metadata,
                recorded_at
            ) VALUES (
                '{transaction_id}',
                NULL,
                'revenue',
                {amount_cents},
                'usd',
                'stripe',
                '{metadata or {}}'::jsonb,
                '{datetime.now(timezone.utc).isoformat()}'
            )
        """)
        
        return {
            'success': True,
            'transaction_id': transaction_id,
            'payment_intent_id': payment_intent_id
        }
    except Exception as e:
        return {'error': str(e)}
