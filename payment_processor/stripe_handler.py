import stripe
from datetime import datetime
from typing import Dict, Any, Optional
from core.database import query_db

async def handle_stripe_webhook(payload: Dict[str, Any], sig_header: str) -> Dict[str, Any]:
    """Handle incoming Stripe webhooks for payment events."""
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            stripe.webhook_secret
        )

        if event.type == 'payment_intent.succeeded':
            return await _handle_successful_payment(event.data.object)
        elif event.type == 'invoice.paid':
            return await _handle_subscription_payment(event.data.object)
        elif event.type == 'customer.subscription.deleted':
            return await _handle_subscription_canceled(event.data.object)

        return {"status": "unhandled_event"}
    except Exception as e:
        return {"error": str(e), "status": "error"}

async def _create_revenue_event(event_data: Dict[str, Any], event_type: str) -> Optional[Dict[str, Any]]:
    """Create a revenue event record in database."""
    try:
        amount_cents = int(float(event_data.get('amount', 0)) * 100)
        metadata = event_data.get('metadata', {})

        query = f"""
        INSERT INTO revenue_events (
            id, 
            event_type,
            amount_cents,
            currency,
            source,
            metadata,
            recorded_at,
            created_at
        ) VALUES (
            gen_random_uuid(),
            '{event_type}',
            {amount_cents},
            '{event_data.get('currency', 'usd')}',
            'stripe',
            '{json.dumps(metadata)}',
            NOW(),
            NOW()
        )
        """
        
        result = await query_db(query)
        return result
    except Exception as e:
        print(f"Failed to create revenue event: {str(e)}")
        return None
