from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum
import json
import uuid
import logging

from dateutil.relativedelta import relativedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BillingFrequency(Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class SubscriptionManager:
    """Manages subscription billing cycles and invoicing."""
    
    def __init__(self, db_execute: callable, db_query: callable):
        self.db_execute = db_execute
        self.db_query = db_query
        
    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        billing_frequency: BillingFrequency,
        start_date: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Create a new subscription."""
        start_date = start_date or datetime.utcnow()
        sub_id = str(uuid.uuid4())
        
        if billing_frequency == BillingFrequency.MONTHLY:
            interval = 1
            interval_unit = 'month'
        elif billing_frequency == BillingFrequency.QUARTERLY:
            interval = 3
            interval_unit = 'month'
        else:  # annual
            interval = 1
            interval_unit = 'year'
            
        next_billing_date = start_date + relativedelta(**{f"{interval_unit}s": interval})
        
        await self.db_execute(
            f"""
            INSERT INTO subscriptions (
                id, customer_id, plan_id, status,
                billing_frequency, start_date,
                next_billing_date, metadata
            ) VALUES (
                '{sub_id}', '{customer_id}', '{plan_id}',
                'active', '{billing_frequency.value}',
                '{start_date.isoformat()}', '{next_billing_date.isoformat()}',
                '{json.dumps(metadata or {})}'::jsonb
            )
            """
        )
        
        logger.info(f"Created subscription {sub_id} for customer {customer_id}")
        return {"subscription_id": sub_id, "next_billing_date": next_billing_date}
        
    async def process_billing_cycle(self) -> Dict[str, Any]:
        """Process all subscriptions due for billing."""
        try:
            # Get subscriptions due for billing
            result = await self.db_query(
                """
                SELECT s.id, s.customer_id, s.plan_id, p.amount_cents, p.currency
                FROM subscriptions s
                JOIN plans p ON s.plan_id = p.id
                WHERE s.status = 'active'
                AND s.next_billing_date <= NOW()
                LIMIT 1000
                """
            )
            subscriptions = result.get("rows", [])
            
            processed = 0
            failures = []
            
            for sub in subscriptions:
                try:
                    # Process payment
                    payment_data = {
                        "customer_id": sub["customer_id"],
                        "amount": sub["amount_cents"] / 100,
                        "currency": sub["currency"],
                        "description": f"Subscription payment for {sub['plan_id']}",
                        "metadata": {
                            "subscription_id": sub["id"],
                            "billing_cycle": "recurring"
                        }
                    }
                    
                    # Charge the customer (integration with payment processor would be here)
                    # Update next billing date
                    billing_freq = await self.db_query(
                        f"SELECT billing_frequency FROM subscriptions WHERE id = '{sub['id']}'"
                    )
                    freq = billing_freq.get("rows", [{}])[0].get("billing_frequency")
                    
                    if freq == BillingFrequency.MONTHLY.value:
                        new_date = datetime.utcnow() + relativedelta(months=1)
                    elif freq == BillingFrequency.QUARTERLY.value:
                        new_date = datetime.utcnow() + relativedelta(months=3)
                    else:  # annual
                        new_date = datetime.utcnow() + relativedelta(years=1)
                    
                    await self.db_execute(
                        f"""
                        UPDATE subscriptions
                        SET next_billing_date = '{new_date.isoformat()}',
                            last_billed_at = NOW()
                        WHERE id = '{sub['id']}'
                        """
                    )
                    
                    await self.db_execute(
                        f"""
                        INSERT INTO revenue_events (
                            id, event_type, amount_cents, currency,
                            source, recorded_at, metadata
                        ) VALUES (
                            gen_random_uuid(), 'recurring_revenue', {sub['amount_cents']},
                            '{sub['currency']}', 'subscription', NOW(),
                            '{json.dumps({
                                'subscription_id': sub['id'],
                                'plan_id': sub['plan_id'],
                                'customer_id': sub['customer_id'],
                                'billing_cycle': freq
                            })}'::jsonb
                        )
                        """
                    )
                    
                    processed += 1
                except Exception as e:
                    failures.append({"subscription_id": sub["id"], "error": str(e)})
                    logger.error(f"Failed to process subscription {sub['id']}: {str(e)}")
            
            return {
                "success": True,
                "processed": processed,
                "failed": len(failures),
                "failures": failures[:10]
            }
            
        except Exception as e:
            logger.error(f"Billing cycle processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
