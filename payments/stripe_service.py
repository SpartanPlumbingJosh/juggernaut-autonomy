import os
import stripe
from typing import Dict, Optional
from datetime import datetime

from core.database import query_db
from core.logging import log_action

stripe.api_key = os.getenv('STRIPE_API_KEY')

class StripePaymentService:
    """Handle all Stripe payment operations."""

    def create_payment_intent(self, amount: int, currency: str, metadata: Dict) -> Dict:
        """Create a new payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata,
                payment_method_types=['card'],
            )
            log_action("payment.created", f"Created payment intent {intent.id}")
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id
            }
        except Exception as e:
            log_action("payment.failed", f"Payment creation failed: {str(e)}", level="error")
            return {"success": False, "error": str(e)}

    def record_payment_event(self, event_data: Dict) -> Dict:
        """Record a Stripe webhook payment event."""
        try:
            event_type = event_data['type']
            payment_intent = event_data['data']['object']
            
            sql = f"""
            INSERT INTO payment_events (
                id, payment_intent_id, amount, currency, 
                status, event_type, event_data, created_at
            ) VALUES (
                gen_random_uuid(),
                '{payment_intent['id']}',
                {payment_intent['amount']},
                '{payment_intent['currency']}',
                '{payment_intent['status']}',
                '{event_type}',
                '{json.dumps(payment_intent)}'::jsonb,
                NOW()
            )
            """
            
            query_db(sql)
            log_action("payment.event_recorded", f"Recorded {event_type} for {payment_intent['id']}")
            
            # For successful payments, create revenue event
            if event_type == 'payment_intent.succeeded':
                self._create_revenue_event(payment_intent)
            
            return {"success": True}
        except Exception as e:
            log_action("payment.event_failed", f"Failed to record event: {str(e)}", level="error")
            return {"success": False, "error": str(e)}

    def _create_revenue_event(self, payment_intent: Dict) -> None:
        """Create revenue event from successful payment."""
        metadata = payment_intent.get('metadata', {})
        
        sql = f"""
        INSERT INTO revenue_events (
            id, amount_cents, currency, source,
            event_type, metadata, recorded_at
        ) VALUES (
            gen_random_uuid(),
            {payment_intent['amount']},
            '{payment_intent['currency']}',$B
            'stripe',
            'revenue',
            '{json.dumps(metadata)}'::jsonb,
            NOW()
        )
        """
        query_db(sql)
        log_action("revenue.created", f"Created revenue from payment {payment_intent['id']}")
