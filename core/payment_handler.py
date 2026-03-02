from datetime import datetime, timezone
from typing import Any, Dict

from core.database import execute_sql

async def handle_payment_webhook(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process payment webhook events from Stripe/PayPal/etc."""
    try:
        payment_id = data.get("id")
        amount_cents = int(float(data.get("amount")) * 100)  # Convert to cents
        currency = data.get("currency", "USD").upper()
        customer_id = data.get("customer")
        metadata = data.get("metadata", {})

        # Dedupe check
        existing = await execute_sql(
            f"""SELECT id FROM revenue_events 
                WHERE metadata->>'payment_id' = '{payment_id}'"""
        )
        if existing.get("rows"):
            return {"success": True, "existing": True}

        # Record revenue event
        await execute_sql(
            f"""INSERT INTO revenue_events (
                id, experiment_id, event_type, 
                amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(), 
                '{metadata.get("experiment_id", "")}',
                'revenue',
                {amount_cents},
                '{currency}',
                '{data.get("payment_method", "unknown")}',
                '{json.dumps(metadata)}',
                NOW(),
                NOW()
            )"""
        )

        return {"success": True, "processed": True}

    except Exception as e:
        return {"success": False, "error": str(e)}
