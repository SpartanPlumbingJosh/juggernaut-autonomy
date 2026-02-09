import stripe
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.database import query_db

class PaymentService:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.stripe = stripe

    async def create_checkout_session(
        self,
        price_id: str,
        user_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create Stripe checkout session"""
        session = self.stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'user_id': user_id,
                **(metadata or {})
            }
        )
        return session

    async def log_transaction(
        self,
        amount_cents: int,
        currency: str,
        source: str,
        user_id: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Log revenue transaction to database"""
        await query_db(f"""
            INSERT INTO revenue_events (
                id, 
                event_type,
                amount_cents,
                currency,
                source,
                user_id,
                metadata,
                recorded_at,
                created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                '{currency}',
                '{source}',
                '{user_id}',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
        """)
