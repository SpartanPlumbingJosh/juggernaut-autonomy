import stripe
import logging
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.logger = logging.getLogger(__name__)

    async def create_payment_intent(
        self,
        amount_cents: int,
        currency: str = "usd",
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create a Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True},
            )
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id
            }
        except Exception as e:
            self.logger.error(f"Payment intent creation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def record_payment_event(
        self,
        execute_sql: Callable[[str], Dict[str, Any]],
        payment_intent_id: str,
        amount_cents: int,
        user_id: str,
        product_id: str
    ) -> Dict:
        """Record successful payment in revenue_events."""
        try:
            await execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {amount_cents},
                    'usd',
                    'stripe',
                    '{{"payment_intent_id": "{payment_intent_id}", "user_id": "{user_id}", "product_id": "{product_id}"}}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            return {"success": True}
        except Exception as e:
            self.logger.error(f"Failed to record payment: {str(e)}")
            return {"success": False, "error": str(e)}
