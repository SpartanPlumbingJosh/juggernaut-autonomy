import stripe
from typing import Dict, Any, Optional
from datetime import datetime
from core.database import execute_sql

STRIPE_SECRET_KEY = "your_stripe_secret_key"
WEBHOOK_SECRET = "your_stripe_webhook_secret"

stripe.api_key = STRIPE_SECRET_KEY

async def create_checkout_session(product_id: str, price_id: str, user_id: str) -> Dict[str, Any]:
    """Create a Stripe checkout session."""
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f'https://example.com/success?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url='https://example.com/cancel',
            client_reference_id=user_id,
            metadata={
                'product_id': product_id,
                'user_id': user_id
            }
        )
        return {'session_id': session.id, 'url': session.url}
    except Exception as e:
        return {'error': str(e)}

async def handle_stripe_webhook(payload: str, signature: str) -> Dict[str, Any]:
    """Handle Stripe webhook events."""
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, WEBHOOK_SECRET
        )
    except ValueError as e:
        return {'error': 'Invalid payload'}
    except stripe.error.SignatureVerificationError as e:
        return {'error': 'Invalid signature'}

    event_type = event['type']
    data = event['data']['object']

    if event_type == 'checkout.session.completed':
        return await handle_checkout_completed(data)
    elif event_type == 'invoice.paid':
        await record_revenue_event(
            event_type='revenue',
            amount=data['amount_paid'] / 100,
            currency=data['currency'],
            subscription_id=data['subscription'],
            metadata={
                'invoice_id': data['id'],
                'period_start': datetime.fromtimestamp(data['period_start']).isoformat(),
                'period_end': datetime.fromtimestamp(data['period_end']).isoformat()
            }
        )
        return {'success': True}
    elif event_type == 'invoice.payment_failed':
        await execute_sql(
            f"""
            UPDATE users
            SET subscription_status = 'payment_failed'
            WHERE subscription_id = '{data['subscription']}'
            """
        )
        return {'success': True}
    elif event_type == 'customer.subscription.deleted':
        await execute_sql(
            f"""
            UPDATE users
            SET subscription_status = 'canceled'
            WHERE subscription_id = '{data['id']}'
            """
        )
        return {'success': True}

    return {'status': 'received but no action taken'}

async def handle_checkout_completed(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle successful checkout session."""
    user_id = data.get('client_reference_id')
    subscription_id = data.get('subscription')

    if not user_id or not subscription_id:
        return {'error': 'Missing required data'}

    await execute_sql(
        f"""
        UPDATE users 
        SET stripe_customer_id = '{data.get('customer')}',
            subscription_id = '{subscription_id}',
            subscription_status = 'active',
            updated_at = NOW()
        WHERE id = '{user_id}'
        """
    )
    return {'success': True}

async def record_revenue_event(
    event_type: str,
    amount: float,
    currency: str,
    subscription_id: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Record revenue/cost event in database."""
    cents = int(amount * 100)
    await execute_sql(
        f"""
        INSERT INTO revenue_events (
            id, event_type, amount_cents, currency,
            subscription_id, metadata, recorded_at
        ) VALUES (
            gen_random_uuid(), '{event_type}', {cents}, 
            '{currency}', '{subscription_id}', 
            '{json.dumps(metadata)}', NOW()
        )
        """
    )
    return {'success': True}
