"""
Minimal Stripe payment integration for immediate revenue collection.
"""
import stripe
from typing import Dict, Optional
from datetime import datetime
from core.config import STRIPE_API_KEY

stripe.api_key = STRIPE_API_KEY

async def create_payment_intent(
    amount_cents: int,
    currency: str = 'usd',
    metadata: Optional[Dict] = None
) -> Dict:
    """Create a Stripe PaymentIntent for immediate collection."""
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            metadata=metadata or {},
            payment_method_types=['card'],
            capture_method='automatic'
        )
        return {
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id,
            'status': intent.status
        }
    except stripe.error.StripeError as e:
        return {'error': str(e)}

async def capture_payment(payment_intent_id: str) -> Dict:
    """Confirm and capture a previously created payment intent."""
    try:
        intent = stripe.PaymentIntent.capture(payment_intent_id)
        return {
            'success': True,
            'amount_captured': intent.amount_received,
            'currency': intent.currency,
            'status': intent.status
        }
    except stripe.error.StripeError as e:
        return {'error': str(e)}

async def record_revenue_event(
    execute_sql: callable,
    payment_intent_id: str,
    amount_cents: int,
    product_id: str,
    customer_id: str
) -> Dict:
    """Record successful payment in our revenue system."""
    sql = f"""
    INSERT INTO revenue_events (
        id, event_type, amount_cents, currency, 
        product_id, customer_id, payment_intent_id,
        recorded_at, created_at
    ) VALUES (
        gen_random_uuid(),
        'revenue',
        {amount_cents},
        'usd',
        '{product_id}',
        '{customer_id}',
        '{payment_intent_id}',
        NOW(),
        NOW()
    )
    """
    await execute_sql(sql)
    return {'success': True}
