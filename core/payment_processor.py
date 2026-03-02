import stripe
import logging
from datetime import datetime
from typing import Dict, Optional

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.logger = logging.getLogger(__name__)

    async def create_payment_intent(self, amount_cents: int, currency: str = "usd", metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent for a specific amount."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata or {},
                payment_method_types=['card'],
            )
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "amount_cents": amount_cents,
                "currency": currency,
                "status": intent.status
            }
        except Exception as e:
            self.logger.error(f"Payment intent creation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def record_revenue_event(self, execute_sql: Callable[[str], Dict[str, Any]], 
                                 payment_intent_id: str, amount_cents: int, 
                                 source: str, metadata: Dict) -> Dict:
        """Record a successful payment as a revenue event."""
        try:
            sql = f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                'usd',
                '{source.replace("'", "''")}',
                '{json.dumps(metadata).replace("'", "''")}',
                NOW(),
                NOW()
            )
            """
            await execute_sql(sql)
            return {"success": True}
        except Exception as e:
            self.logger.error(f"Revenue event recording failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                return await self._handle_payment_success(payment_intent)
                
            return {"success": True, "handled": False}
        except Exception as e:
            self.logger.error(f"Webhook processing failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _handle_payment_success(self, payment_intent: Dict) -> Dict:
        """Handle successful payment event."""
        metadata = payment_intent.get('metadata', {})
        source = metadata.get('source', 'stripe')
        
        return {
            "success": True,
            "handled": True,
            "payment_intent_id": payment_intent['id'],
            "amount_cents": payment_intent['amount'],
            "source": source,
            "metadata": metadata
        }
