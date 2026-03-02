import os
import stripe
from datetime import datetime, timedelta
from typing import Dict, List
from core.database import query_db
from core.logging import logger

class SubscriptionManager:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_API_KEY')

    async def process_recurring_payments(self) -> Dict:
        """Process all due recurring payments."""
        try:
            # Get subscriptions with due payments
            result = await query_db("""
                SELECT id, stripe_subscription_id, customer_email 
                FROM subscriptions 
                WHERE next_payment_date <= NOW()
                AND status = 'active'
                LIMIT 100
            """)
            subscriptions = result.get('rows', [])

            processed = 0
            for sub in subscriptions:
                success = await self._process_single_payment(sub)
                if success:
                    processed += 1

            return {
                'success': True,
                'processed': processed,
                'total': len(subscriptions)
            }
        except Exception as e:
            logger.error(f"Recurring payment processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def _process_single_payment(self, subscription: Dict) -> bool:
        try:
            # Attempt payment via Stripe
            payment_intent = stripe.PaymentIntent.create(
                amount=subscription['amount_due'],
                currency='usd',
                customer=subscription['stripe_customer_id'],
                payment_method=subscription['stripe_payment_method_id'],
                off_session=True,
                confirm=True
            )

            if payment_intent.status == 'succeeded':
                await self._record_successful_payment(subscription, payment_intent)
                return True
            return False
        except stripe.error.CardError as e:
            logger.warning(f"Payment failed for {subscription['id']}: {str(e)}")
            await self._handle_payment_failure(subscription)
            return False

    async def _record_successful_payment(self, subscription: Dict, payment_intent: Dict) -> None:
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {payment_intent['amount']},
                '{payment_intent['currency']}',
                'stripe-subscription',
                '{json.dumps({
                    'subscription_id': subscription['id'],
                    'payment_intent': payment_intent['id'],
                    'invoice_id': payment_intent.get('invoice')
                })}',
                NOW()
            );

            UPDATE subscriptions 
            SET last_payment_date = NOW(),
                next_payment_date = NOW() + INTERVAL '1 month',
                payments_count = payments_count + 1
            WHERE id = '{subscription['id']}'
            """
        )
