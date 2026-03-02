import hmac
import hashlib
from datetime import datetime
from typing import Dict, Any
from core.database import query_db

async def verify_paddle_webhook(payload: Dict[str, Any], signature: str) -> bool:
    """Verify Paddle webhook signature."""
    public_key = "YOUR_PADDLE_PUBLIC_KEY"
    sig = hmac.new(public_key.encode(), payload.encode(), hashlib.sha1).hexdigest()
    return hmac.compare_digest(sig, signature)

async def handle_paddle_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle incoming Paddle webhooks."""
    event_type = payload.get('alert_name')
    
    if event_type == 'payment_succeeded':
        return await _handle_paddle_payment(payload)
    elif event_type == 'subscription_created':
        return await _handle_subscription_created(payload)
    elif event_type == 'subscription_cancelled':
        return await _handle_subscription_cancelled(payload)

    return {"status": "unhandled_event"}

async def _create_paddle_revenue(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create revenue record for Paddle payment."""
    try:
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
            'revenue',
            {int(float(payload.get('sale_gross', 0)) * 100)},
            '{payload.get('currency', 'USD')}',
            'paddle',
            '{json.dumps(payload)}',
            NOW(),
            NOW()
        )
        """
        return await query_db(query)
    except Exception as e:
        print(f"Failed to create Paddle revenue event: {str(e)}")
        return None
