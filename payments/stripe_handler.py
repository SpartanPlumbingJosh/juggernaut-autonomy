"""
Handle Stripe payment processing webhooks and events.
Creates revenue events and triggers fulfillment.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from core.database import query_db


async def handle_stripe_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process Stripe webhook event and create revenue record.
    Returns dict with status and any errors.
    """
    event_type = event.get('type')
    data = event.get('data', {}).get('object', {})
    
    if not event_type or not data:
        return {'status': 'error', 'error': 'Missing event type or data'}
    
    logger = logging.getLogger('stripe')
    
    try:
        if event_type == 'payment_intent.succeeded':
            await _process_payment(data)
        elif event_type == 'charge.refunded':
            await _process_refund(data)
        else:
            logger.info(f"Skipping unhandled Stripe event: {event_type}")
            return {'status': 'skipped', 'event_type': event_type}
            
        return {'status': 'success'}
    except Exception as e:
        logger.error(f"Failed processing Stripe event: {str(e)}")
        return {'status': 'error', 'error': str(e)}


async def _process_payment(charge: Dict[str, Any]) -> None:
    """Record successful payment in revenue events."""
    amount = charge.get('amount')
    currency = charge.get('currency')
    customer = charge.get('customer')
    metadata = charge.get('metadata', {})
    
    sql = f"""
    INSERT INTO revenue_events (
        id,
        event_type,
        amount_cents,
        currency,
        source,
        recorded_at,
        metadata
    ) VALUES (
        gen_random_uuid(),
        'revenue',
        {amount},
        '{currency}',
        'stripe_payment',
        '{datetime.now(timezone.utc).isoformat()}',
        '{metadata}'
    )
    """
    
    await query_db(sql)
    
    # Trigger product fulfillment
    product_id = metadata.get('product_id')
    if product_id:
        await _fulfill_order(product_id, customer, amount)


async def _process_refund(charge: Dict[str, Any]) -> None:
    """Record refund in revenue events as negative amount."""
    amount = charge.get('amount_refunded', 0)
    currency = charge.get('currency')
    
    sql = f"""
    INSERT INTO revenue_events (
        id,
        event_type,
        amount_cents,
        currency,
        source,
        recorded_at
    ) VALUES (
        gen_random_uuid(),
        'revenue',
        -{amount},
        '{currency}',
        'stripe_refund',
        '{datetime.now(timezone.utc).isoformat()}'
    )
    """
    
    await query_db(sql)


async def _fulfill_order(product_id: str, customer: str, amount: int) -> None:
    """
    Trigger product/service delivery based on product ID.
    Can be extended with different fulfillment workflows.
    """
    logger = logging.getLogger('stripe')
    
    try:
        # Example: Send license key for digital product
        if product_id.startswith('dig_'):
            license_key = f"LIC-{product_id}-{customer[:4]}"
            sql = f"""
            INSERT INTO product_deliveries (
                id,
                product_id,
                customer_id,
                license_key,
                delivered_at,
                amount_cents
            ) VALUES (
                gen_random_uuid(),
                '{product_id}',
                '{customer}',
                '{license_key}',
                NOW(),
                {amount}
            )
            """
            await query_db(sql)
            
            # In real implementation would email license here
            logger.info(f"Digital product fulfilled: {product_id}")
            
        else:
            logger.warning(f"Unhandled product ID format: {product_id}")
            
    except Exception as e:
        logger.error(f"Failed to fulfill order: {str(e)}")
        raise

