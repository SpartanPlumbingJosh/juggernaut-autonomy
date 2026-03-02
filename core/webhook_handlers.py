import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from core.payment_processor import PaymentProcessor
from core.database import query_db, execute_db

logger = logging.getLogger(__name__)


class PaymentWebhookHandler:
    def __init__(self, payment_processor: PaymentProcessor):
        self.processor = payment_processor

    async def handle_stripe_event(self, payload: bytes, sig_header: str) -> Tuple[bool, Dict[str, Any]]:
        """Validate and process Stripe webhook event."""
        try:
            event = self.processor.stripe.Webhook.construct_event(
                payload, sig_header, stripe_webhook_secret
            )
            
            await self.processor.record_payment_event(event)
            
            if event.type == 'invoice.payment_succeeded':
                return await self._handle_payment_success(event)
            elif event.type == 'invoice.payment_failed':
                return await self._handle_payment_failure(event)
            elif event.type == 'customer.subscription.deleted':
                return await self._handle_subscription_cancel(event)
                
            return True, {'status': 'processed'}
        except Exception as e:
            logger.error(f"Failed to handle Stripe event: {str(e)}")
            return False, {'error': str(e)}

    async def _handle_payment_success(self, event: Any) -> Tuple[bool, Dict[str, Any]]:
        """Process successful payment."""
        invoice = event['data']['object']
        amount = invoice['amount_due'] / 100  # Convert to dollars
        customer_id = invoice['customer']
        
        await execute_db(
            """
            INSERT INTO revenue_events 
            (experiment_id, event_type, amount_cents, currency, source, recorded_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            (None, 'revenue', amount * 100, 'usd', 'stripe')
        )
        
        return True, {'amount': amount, 'customer_id': customer_id}

    async def _handle_payment_failure(self, event: Any) -> Tuple[bool, Dict[str, Any]]:
        """Process payment failure and trigger dunning."""
        invoice = event['data']['object']
        attempt_count = invoice['attempt_count']
        customer_id = invoice['customer']
        
        if attempt_count >= 3:
            await self._cancel_subscription(customer_id)
            logger.warning(f"Canceled subscription for {customer_id} after payment failure")
            
        return True, {'attempt_count': attempt_count, 'customer_id': customer_id}

    async def _handle_subscription_cancel(self, event: Any) -> Tuple[bool, Dict[str, Any]]:
        """Process subscription cancellation."""
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        await execute_db(
            """
            UPDATE subscriptions
            SET status = 'canceled', ended_at = NOW()
            WHERE stripe_id = %s
            """,
            (subscription.id,)
        )
        
        return True, {'customer_id': customer_id}
