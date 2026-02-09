import json
from typing import Dict, Any
from datetime import datetime
from core.database import query_db

async def handle_payment_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process payment webhook events and update revenue database."""
    event_type = event.get("type")
    data = event.get("data", {})
    
    # Handle payment success
    if event_type == "payment.succeeded":
        payment_id = data.get("id")
        amount = int(float(data.get("amount", 0)) * 100)  # Convert to cents
        currency = data.get("currency", "usd")
        customer_email = data.get("customer_email", "")
        created_at = datetime.fromtimestamp(data.get("created", 0))
        
        # Record revenue event
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                '{payment_id}', 'revenue', {amount}, '{currency}',
                'payment', '{json.dumps({"customer_email": customer_email})}',
                '{created_at.isoformat()}', NOW()
            )
        """)
        
        return {"success": True, "message": "Payment recorded"}
    
    return {"success": False, "error": "Unhandled event type"}

__all__ = ["handle_payment_webhook"]
