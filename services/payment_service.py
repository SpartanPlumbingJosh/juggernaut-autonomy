import stripe
from typing import Dict, Any
from datetime import datetime
from core.database import query_db

class PaymentService:
    def __init__(self, api_key: str):
        stripe.api_key = api_key

    async def create_checkout_session(
        self,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create a Stripe checkout session."""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata or {}
            )
            return {"success": True, "session_id": session.id, "url": session.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def record_transaction(
        self,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record a successful payment in our database."""
        payment_intent = event_data['data']['object']
        amount = payment_intent['amount']
        currency = payment_intent['currency']
        metadata = payment_intent.get('metadata', {})

        sql = f"""
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
            {amount},
            '{currency}',
            'stripe',
            '{json.dumps(metadata)}',
            NOW(),
            NOW()
        )
        """
        
        try:
            await query_db(sql)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
