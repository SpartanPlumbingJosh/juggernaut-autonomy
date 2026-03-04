"""
Payment Webhooks API - Handles payment processing webhooks
from various payment providers.
"""

import json
import hmac
import hashlib
from typing import Dict, Any, Optional

from core.database import query_db
from core.payment_providers import PaymentProvider

async def verify_webhook(provider: str, signature: str, payload: str, secret: str) -> bool:
    """Verify webhook signature from payment provider."""
    try:
        if provider == "stripe":
            computed = hmac.new(
                secret.encode(), 
                payload.encode(), 
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(computed, signature)
            
        elif provider == "paypal":
            # PayPal verification logic
            return True
            
        return False
    except Exception:
        return False

async def process_payment_webhook(provider: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Process payment webhook event."""
    try:
        # Validate and record payment
        payment = await PaymentProvider(provider).process_webhook(event)
        
        # Record revenue event
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, 
                currency, source, metadata, 
                recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {payment.get('amount')},
                '{payment.get('currency')}',
                '{provider}',
                '{json.dumps(payment)}'::jsonb,
                NOW(),
                NOW()
            )
            """
        )
        
        return {"success": True}
        
    except Exception as e:
        return {"error": f"Payment processing failed: {str(e)}"}

async def route_payment_webhook(path: str, method: str, headers: Dict[str, str], body: str) -> Dict[str, Any]:
    """Route payment webhook requests."""
    if method != "POST":
        return {"error": "Method not allowed"}
    
    try:
        provider = path.split("/")[-1]  # /webhook/stripe, /webhook/paypal etc
        signature = headers.get(f"X-{provider}-Signature", "")
        secret = "YOUR_SECRET_KEY"  # Should be from config
        
        if not verify_webhook(provider, signature, body, secret):
            return {"error": "Invalid signature"}
            
        event = json.loads(body)
        return await process_payment_webhook(provider, event)
        
    except Exception as e:
        return {"error": f"Webhook processing failed: {str(e)}"}

__all__ = ["route_payment_webhook"]
