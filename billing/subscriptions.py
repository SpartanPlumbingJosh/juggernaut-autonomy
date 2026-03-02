"""Subscription management and recurring billing logic."""

import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from croniter import croniter
from dateutil.relativedelta import relativedelta

from core.database import query_db
from core.logging import get_logger
from .service import BillingService

logger = get_logger(__name__)

class SubscriptionManager:
    def __init__(self):
        self.billing = BillingService()

    async def create_subscription(
        self,
        customer_id: str,
        processor: str,
        plan_id: str,
        billing_cycle: str = 'monthly',
        start_date: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Create a new subscription"""
        start_date = start_date or datetime.now(timezone.utc)
        try:
            subscription = {
                'customer_id': customer_id,
                'processor': processor,
                'plan_id': plan_id,
                'billing_cycle': billing_cycle,
                'status': 'active',
                'start_date': start_date,
                'next_billing_date': self._calculate_next_billing(start_date, billing_cycle),
                'metadata': metadata or {}
            }
            
            await query_db(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, processor, plan_id, 
                    billing_cycle, status, start_date,
                    next_billing_date, metadata, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{processor}',
                    '{plan_id}',
                    '{billing_cycle}',
                    'active',
                    '{start_date.isoformat()}',
                    '{subscription['next_billing_date'].isoformat()}',
                    '{json.dumps(metadata or {})}',
                    NOW()
                )
                RETURNING id
                """
            )
            
            return subscription
        except Exception as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            return None

    def _calculate_next_billing(self, start_date: datetime, cycle: str) -> datetime:
        """Calculate next billing date based on cycle"""
        if cycle == 'monthly':
            return start_date + relativedelta(months=+1)
        elif cycle == 'yearly':
            return start_date + relativedelta(years=+1)
        elif cycle == 'weekly':
            return start_date + timedelta(weeks=1)
        else:
            # Custom cron expression
            iter = croniter(cycle, start_date)
            return iter.get_next(datetime)

    async def process_due_subscriptions(self) -> Dict:
        """Process all subscriptions due for billing"""
        try:
            now = datetime.now(timezone.utc)
            due_subs = await query_db(
                f"""
                SELECT * FROM subscriptions
                WHERE status = 'active'
                AND next_billing_date <= '{now.isoformat()}'
                FOR UPDATE SKIP LOCKED
                """
            )
            
            results = {'success': [], 'failed': []}
            for sub in due_subs.get('rows', []):
                try:
                    invoice = await self.billing.create_invoice(sub['id'])
                    await query_db(
                        f"""
                        UPDATE subscriptions
                        SET last_billed_at = NOW(),
                            next_billing_date = '{self._calculate_next_billing(now, sub['billing_cycle'])}'
                        WHERE id = '{sub['id']}'
                        """
                    )
                    results['success'].append(sub['id'])
                except Exception:
                    results['failed'].append(sub['id'])
            
            return results
        except Exception as e:
            logger.error(f"Subscription processing failed: {str(e)}")
            return {'success': [], 'failed': []}
