"""
Webhook handlers for payment processing events.
"""
from typing import Dict, Any, Optional
import logging
from datetime import datetime
from .models import SubscriptionStatus, InvoiceStatus

logger = logging.getLogger(__name__)

class WebhookHandler:
    def __init__(self, db_executor):
        self.db_executor = db_executor

    async def handle_stripe_event(self, event: Dict[str, Any]) -> bool:
        event_type = event.get('type')
        data = event.get('data', {}).get('object', {})
        
        try:
            if event_type.startswith('customer.subscription.'):
                return await self._handle_subscription_event(event_type, data)
            elif event_type.startswith('invoice.'):
                return await self._handle_invoice_event(event_type, data)
            elif event_type.startswith('payment_method.'):
                return await self._handle_payment_method_event(event_type, data)
        except Exception as e:
            logger.error(f"Failed to process Stripe event {event_type}: {str(e)}")
            return False
        
        logger.debug(f"Unhandled Stripe event type: {event_type}")
        return True

    async def _handle_subscription_event(self, event_type: str, data: Dict[str, Any]) -> bool:
        sub_id = data.get('id')
        customer_id = data.get('customer')
        status = data.get('status')
        
        if not sub_id or not customer_id:
            return False
            
        if event_type == 'customer.subscription.deleted':
            status = 'canceled'
        
        # Update subscription in database
        await self.db_executor(
            f"""
            INSERT INTO subscriptions (id, customer_id, status, current_period_start, 
                                     current_period_end, updated_at)
            VALUES ('{sub_id}', '{customer_id}', '{status}', 
                    '{data.get('current_period_start')}', 
                    '{data.get('current_period_end')}', 
                    NOW())
            ON CONFLICT (id) DO UPDATE
            SET status = EXCLUDED.status,
                current_period_start = EXCLUDED.current_period_start,
                current_period_end = EXCLUDED.current_period_end,
                updated_at = NOW()
            """
        )
        
        if status == 'past_due':
            logger.info(f"Subscription {sub_id} is past due - sending reminder")
            # TODO: Trigger dunning process
            
        return True

    async def _handle_invoice_event(self, event_type: str, data: Dict[str, Any]) -> bool:
        invoice_id = data.get('id')
        customer_id = data.get('customer')
        status = data.get('status')
        paid = data.get('paid')
        
        if not invoice_id or not customer_id:
            return False
            
        if event_type == 'invoice.payment_succeeded' and paid:
            status = 'paid'
            paid_at = datetime.utcnow().isoformat()
            
            # Record revenue event
            await self._record_revenue_event(
                customer_id=customer_id,
                amount=data.get('amount_paid', 0),
                currency=data.get('currency'),
                invoice_id=invoice_id,
                subscription_id=data.get('subscription')
            )
        else:
            paid_at = None
            
        await self.db_executor(
            f"""
            INSERT INTO invoices (id, customer_id, status, amount_due, currency,
                                subscription_id, paid_at, updated_at)
            VALUES ('{invoice_id}', '{customer_id}', '{status}', 
                    {data.get('amount_due', 0)}, 
                    '{data.get('currency', 'usd')}',
                    '{data.get('subscription')}',
                    {'NOW()' if paid_at else 'NULL'},
                    NOW())
            ON CONFLICT (id) DO UPDATE
            SET status = EXCLUDED.status,
                amount_due = EXCLUDED.amount_due,
                paid_at = EXCLUDED.paid_at,
                updated_at = NOW()
            """
        )
        
        if event_type == 'invoice.payment_failed':
            logger.info(f"Invoice {invoice_id} payment failed - starting dunning process")
            # TODO: Trigger dunning process
            
        return True

    async def _record_revenue_event(self, 
                                  customer_id: str,
                                  amount: int,
                                  currency: str,
                                  invoice_id: str,
                                  subscription_id: Optional[str] = None):
        """Record a revenue event in the accounting system."""
        await self.db_executor(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount},
                '{currency}',
                'subscription',
                '{{"invoice_id": "{invoice_id}", "subscription_id": "{subscription_id or ''}"}}'::jsonb,
                NOW()
            )
            """
        )
