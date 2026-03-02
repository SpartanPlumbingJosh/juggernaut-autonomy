"""
Payment webhook handlers for automated revenue collection.
Supports Stripe and PayPal webhook events.
"""

from typing import Dict, Any
import stripe
import paypalrestsdk
from datetime import datetime, timezone

from core.database import query_db
from core.delivery import deliver_product

stripe.api_key = "sk_test_..."  # TODO: Move to config
paypalrestsdk.configure({
    "mode": "sandbox",  # TODO: Move to config
    "client_id": "...",
    "client_secret": "..."
})

async def handle_stripe_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process Stripe payment webhook events."""
    event_type = event.get('type')
    data = event.get('data', {})
    payment_intent = data.get('object', {})
    
    event_id = event.get('id')
    customer_id = payment_intent.get('customer')
    amount = payment_intent.get('amount')  # in cents
    currency = payment_intent.get('currency', 'usd').lower()
    
    if event_type == 'payment_intent.succeeded':
        # Add to revenue tracking
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                customer_id, source, recorded_at, metadata
            ) VALUES (
                gen_random_uuid(), 'revenue', {amount}, '{currency}', 
                '{customer_id}', 'stripe', '{datetime.now(timezone.utc).isoformat()}', 
                '{json.dumps({'stripe_event_id': event_id})}'::jsonb
            )
            """
        )
        
        # Trigger product delivery
        products = await query_db(
            f"SELECT product_id FROM customer_products WHERE customer_id = '{customer_id}'"
        )
        for product in products.get('rows', []):
            deliver_product(product['product_id'], customer_id)
            
        return {'status': 'success'}
        
    return {'status': 'skipped', 'reason': 'unhandled_event_type'}

async def handle_paypal_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process PayPal payment webhook events."""
    # Similar PayPal webhook handling implementation
    # Would include verification of PayPal webhook signature
    pass

async def route_payment_webhook(source: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Route payment webhooks to appropriate handler."""
    try:
        if source == 'stripe':
            return await handle_stripe_webhook(payload)
        elif source == 'paypal':
            return await handle_paypal_webhook(payload)
        return {'status': 'error', 'reason': 'invalid_source'}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}
