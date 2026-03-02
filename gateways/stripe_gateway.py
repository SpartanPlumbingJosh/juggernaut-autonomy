import stripe
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class StripeGateway:
    def __init__(self, api_key: str):
        self.api_key = api_key
        stripe.api_key = api_key

    async def create_customer(self, email: str, name: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new customer in Stripe"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer": customer}
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_payment_intent(self, amount: int, currency: str, customer_id: str, 
                                  metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a payment intent for a customer"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                metadata=metadata or {},
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            return {"success": True, "payment_intent": intent}
        except Exception as e:
            logger.error(f"Failed to create payment intent: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            # Handle specific event types
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                return await self._handle_successful_payment(payment_intent)
            elif event['type'] == 'payment_intent.payment_failed':
                payment_intent = event['data']['object']
                return await self._handle_failed_payment(payment_intent)
            
            return {"success": True, "event": event['type']}
        except Exception as e:
            logger.error(f"Failed to process webhook: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _handle_successful_payment(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment event"""
        try:
            # Extract relevant data
            amount = payment_intent['amount']
            currency = payment_intent['currency']
            customer_id = payment_intent['customer']
            metadata = payment_intent.get('metadata', {})
            
            # Log revenue event
            await self._log_revenue_event(
                amount=amount,
                currency=currency,
                customer_id=customer_id,
                metadata=metadata,
                status='success'
            )
            
            return {"success": True, "message": "Payment succeeded"}
        except Exception as e:
            logger.error(f"Failed to handle successful payment: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _log_revenue_event(self, amount: int, currency: str, customer_id: str,
                               metadata: Dict[str, Any], status: str) -> Dict[str, Any]:
        """Log revenue event to database"""
        try:
            from core.database import query_db
            
            sql = f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount},
                '{currency}',
                'stripe',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
            """
            await query_db(sql)
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to log revenue event: {str(e)}")
            return {"success": False, "error": str(e)}
