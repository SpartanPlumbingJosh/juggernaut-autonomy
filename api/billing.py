"""
Autonomous Billing System - Handles all payment processing
"""
import stripe
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from core.database import query_db
from .revenue_api import _make_response, _error_response

# Initialize payment processor
stripe.api_key = "sk_live_..."  # Should be from env vars

async def process_payment(amount_cents: int, 
                         currency: str,
                         customer_id: str,
                         description: str) -> Dict[str, Any]:
    """Charge a customer through Stripe"""
    try:
        charge = stripe.Charge.create(
            amount=amount_cents,
            currency=currency,
            customer=customer_id,
            description=description,
            metadata={
                "system": "autonomous_revenue",
                "processed_at": datetime.utcnow().isoformat()
            }
        )
        
        # Record in our database
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                '{currency}',
                'stripe',
                '{{
                    "charge_id": "{charge.id}",
                    "description": "{description}",
                    "customer": "{customer_id}"
                }}'::jsonb,
                NOW()
            )
        """)
        
        return _make_response(200, {
            "success": True,
            "charge_id": charge.id,
            "amount": amount_cents,
            "currency": currency
        })
        
    except stripe.error.StripeError as e:
        logging.error(f"Payment failed: {str(e)}")
        return _error_response(400, f"Payment failed: {str(e)}")
