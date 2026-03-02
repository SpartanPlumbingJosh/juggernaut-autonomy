import os
import stripe
import json
from datetime import datetime
from typing import Dict, Any, Optional

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

async def create_payment_intent(amount: int, currency: str = 'usd', metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a Stripe PaymentIntent."""
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            metadata=metadata or {},
            automatic_payment_methods={
                'enabled': True,
            },
        )
        return {
            'client_secret': intent.client_secret,
            'id': intent.id,
            'status': intent.status
        }
    except Exception as e:
        return {'error': str(e)}

async def handle_stripe_webhook(payload: str, sig_header: str) -> Dict[str, Any]:
    """Process Stripe webhook events."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )
    except ValueError as e:
        return {'error': 'Invalid payload'}
    except stripe.error.SignatureVerificationError as e:
        return {'error': 'Invalid signature'}

    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        await fulfill_order(payment_intent)
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        await handle_payment_failure(payment_intent)
    else:
        print(f"Unhandled event type {event['type']}")

    return {'success': True}

async def fulfill_order(payment_intent: Dict[str, Any]) -> None:
    """Handle successful payment and fulfill order."""
    metadata = payment_intent.get('metadata', {})
    amount = payment_intent.get('amount_received', 0)
    
    # Record revenue event
    await query_db(f"""
        INSERT INTO revenue_events (
            id, event_type, amount_cents, currency, source,
            metadata, recorded_at, created_at
        ) VALUES (
            gen_random_uuid(),
            'revenue',
            {amount},
            '{payment_intent['currency']}',
            'stripe',
            '{json.dumps(metadata)}'::jsonb,
            NOW(),
            NOW()
        )
    """)
    
    # Trigger fulfillment based on metadata
    if metadata.get('product_type') == 'subscription':
        await activate_subscription(payment_intent)
    elif metadata.get('product_type') == 'service':
        await deliver_service(payment_intent)

async def activate_subscription(payment_intent: Dict[str, Any]) -> None:
    """Activate subscription for customer."""
    customer_id = payment_intent.get('customer')
    # Implement subscription activation logic
    pass

async def deliver_service(payment_intent: Dict[str, Any]) -> None:
    """Deliver purchased service."""
    metadata = payment_intent.get('metadata', {})
    # Implement service delivery logic
    pass

async def handle_payment_failure(payment_intent: Dict[str, Any]) -> None:
    """Handle failed payment."""
    # Implement failure handling logic
    pass
