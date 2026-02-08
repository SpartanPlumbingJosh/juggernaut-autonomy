"""
Stripe payment gateway integration for revenue experiments.
Handles checkout sessions, webhooks, and service fulfillment.
"""
import os
import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import stripe
from fastapi import HTTPException

from core.database import query_db

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

async def create_checkout_session(
    price_id: str,
    experiment_id: str,
    user_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a Stripe Checkout Session for a given experiment/price.
    Returns the checkout URL for redirect.
    """
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{os.getenv('BASE_URL')}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{os.getenv('BASE_URL')}/payment/cancelled",
            metadata={
                'experiment_id': experiment_id,
                'user_id': user_id,
                'service_type': 'api_key',  # Could also be 'download' or 'account'
                **(metadata or {})
            }
        )
        return {
            'checkout_url': session.url,
            'session_id': session.id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


async def handle_webhook_event(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """
    Process Stripe webhook events.
    Validates signature and handles payment success/failure.
    """
    event = None
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail=f"Invalid signature: {str(e)}")

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        await _fulfill_order(session)

    return {'status': 'success'}


async def _fulfill_order(session: Dict[str, Any]) -> None:
    """
    Fulfill an order by:
    1. Recording transaction in revenue_events
    2. Generating and delivering service (API key, download, etc.)
    """
    experiment_id = session['metadata'].get('experiment_id')
    user_id = session['metadata'].get('user_id')
    service_type = session['metadata'].get('service_type', 'api_key')
    amount_cents = session['amount_total']  # Stripe uses cents
    
    # Generate unique service token
    service_token = str(uuid.uuid4())
    
    # Record revenue event
    await query_db(f"""
        INSERT INTO revenue_events (
            id, experiment_id, event_type, amount_cents, 
            currency, source, metadata, recorded_at
        ) VALUES (
            gen_random_uuid(), 
            '{experiment_id}',
            'revenue',
            {amount_cents},
            '{session['currency']}',
            'stripe',
            '{json.dumps({
                'user_id': user_id,
                'service_type': service_type,
                'stripe_session_id': session['id']
            })}'::jsonb,
            NOW()
        )
    """)
    
    # Fulfill service based on type
    if service_type == 'api_key':
        await _generate_api_key(user_id, service_token)
    # Could add other fulfillment methods here


async def _generate_api_key(user_id: str, token: str) -> None:
    """
    Generate and store an API key for the user.
    """
    await query_db(f"""
        INSERT INTO user_api_keys (
            user_id, api_key, created_at, expires_at
        ) VALUES (
            '{user_id}',
            '{token}',
            NOW(),
            NOW() + INTERVAL '1 year'
        )
        ON CONFLICT (user_id) 
        DO UPDATE SET 
            api_key = EXCLUDED.api_key,
            expires_at = EXCLUDED.expires_at
    """)
