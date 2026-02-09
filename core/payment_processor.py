import stripe
import logging
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        stripe.api_key = api_key
        self.logger = logging.getLogger(__name__)

    def create_payment_intent(self, amount_cents: int, currency: str = "usd", metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent with Stripe."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata or {},
                capture_method="automatic"
            )
            return {
                "success": True,
                "payment_intent_id": intent.id,
                "client_secret": intent.client_secret,
                "status": intent.status
            }
        except stripe.error.StripeError as e:
            self.logger.error(f"Payment intent creation failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "payment_error"
            }

    def capture_payment(self, payment_intent_id: str) -> Dict:
        """Capture a payment."""
        try:
            intent = stripe.PaymentIntent.capture(payment_intent_id)
            return {
                "success": True,
                "payment_intent_id": intent.id,
                "amount_captured": intent.amount_received,
                "status": intent.status
            }
        except stripe.error.StripeError as e:
            self.logger.error(f"Payment capture failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "capture_error"
            }

    def log_revenue_event(self, execute_sql: Callable[[str], Dict[str, Any]], event_data: Dict) -> bool:
        """Log revenue event to database."""
        try:
            execute_sql(f"""
                INSERT INTO revenue_events (
                    id, experiment_id, event_type, amount_cents,
                    currency, source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    {f"'{event_data.get('experiment_id')}'" if event_data.get('experiment_id') else 'NULL'},
                    '{event_data.get('event_type', 'revenue')}',
                    {event_data.get('amount_cents', 0)},
                    '{event_data.get('currency', 'usd')}',
                    '{event_data.get('source', 'stripe')}',
                    '{json.dumps(event_data.get('metadata', {}))}',
                    NOW(),
                    NOW()
                )
            """)
            return True
        except Exception as e:
            self.logger.error(f"Failed to log revenue event: {str(e)}")
            return False
