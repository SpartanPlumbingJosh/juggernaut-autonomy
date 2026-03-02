import logging
from typing import Dict, Any
from .payment_processor import PaymentProcessor

logger = logging.getLogger(__name__)

class RevenueWebhooks:
    """Handle revenue-related webhooks from payment processors."""
    
    def __init__(self, stripe_api_key: str):
        self.processor = PaymentProcessor(stripe_api_key)

    async def handle_stripe_event(self, payload: Dict, sig_header: str) -> bool:
        """Process Stripe webhook event."""
        try:
            event = self.processor.stripe.Webhook.construct_event(
                payload, sig_header, self.processor.stripe.webhook_secret
            )
        except Exception as e:
            logger.error(f"Invalid Stripe webhook: {str(e)}")
            return False

        event_type = event['type']
        
        if event_type == 'payment_intent.succeeded':
            await self.process_payment(event)
        elif event_type == 'invoice.payment_succeeded':
            await self.process_subscription_payment(event)
        elif event_type == 'invoice.payment_failed':
            await self.process_payment_failure(event)

        return True

    async def process_payment(self, event: Dict) -> None:
        """Record successful one-time payment."""
        payment = event['data']['object']
        await execute_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                customer_id, description, metadata,
                recorded_at, created_at
            ) VALUES (
                gen_random_uuid(), 'revenue',
                {payment['amount']}, '{payment['currency']}',
                {f"'{payment['customer']}'" if payment.get('customer') else 'NULL'},
                {f"'{payment['description']}'" if payment.get('description') else 'NULL'},
                '{json.dumps(payment.get('metadata', {}))}'::jsonb,
                NOW(), NOW()
            )
            """
        )

    async def process_subscription_payment(self, event: Dict) -> None:
        """Record successful subscription payment."""
        invoice = event['data']['object']
        sub = invoice['subscription_details']
        
        await execute_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                customer_id, subscription_id, description, 
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(), 'revenue',
                {invoice['amount_paid']}, '{invoice['currency']}',
                '{invoice['customer']}', '{sub['id']}',
                {f"'{invoice['description']}'" if invoice.get('description') else 'NULL'},
                '{json.dumps(invoice.get('metadata', {}))}'::jsonb,
                NOW(), NOW()
            )
            """
        )
