from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from enum import Enum, auto

class SubscriptionStatus(Enum):
    ACTIVE = auto()
    PAUSED = auto()
    CANCELED = auto()
    TRIAL = auto()

class SubscriptionManager:
    """Manage subscription lifecycle and recurring billing."""
    
    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        payment_method_id: str,
        trial_days: int = 0
    ) -> Dict[str, Any]:
        """Create new subscription with initial payment."""
        now = datetime.now()
        trial_end = (now + timedelta(days=trial_days)) if trial_days else None
        
        billing_info = {
            "start_date": now.isoformat(),
            "trial_end": trial_end.isoformat() if trial_end else None,
            "status": SubscriptionStatus.TRIAL.name if trial_days else SubscriptionStatus.ACTIVE.name,
            "next_billing_date": None if trial_days else (now + timedelta(days=30)).isoformat(),
        }
        
        # Record subscription in database
        result = await query_db(f"""
            INSERT INTO subscriptions (
                customer_id,
                plan_id,
                billing_info,
                payment_method_id,
                created_at,
                updated_at
            ) VALUES (
                '{customer_id}',
                '{plan_id}',
                '{json.dumps(billing_info)}'::jsonb,
                '{payment_method_id}',
                NOW(),
                NOW()
            )
            RETURNING id
        """)
        
        return {
            "subscription_id": result["rows"][0]["id"],
            **billing_info
        }

    async def process_recurring_billing(self) -> Dict[str, Any]:
        """Process all subscriptions due for renewal."""
        result = await query_db("""
            SELECT id, customer_id, plan_id, payment_method_id 
            FROM subscriptions 
            WHERE status = 'ACTIVE'
              AND next_billing_date <= NOW()
            LIMIT 1000
        """)
        
        processed = 0
        failures = 0
        
        for sub in result.get("rows", []):
            try:
                payment_result = await PaymentService().create_payment_intent(
                    amount_cents=1000,  # Get actual amount from plan
                    currency="usd",
                    customer_email=sub["customer_id"],
                    metadata={"subscription_id": sub["id"]}
                )
                
                await query_db(f"""
                    UPDATE subscriptions
                    SET 
                        last_payment_date = NOW(),
                        next_billing_date = NOW() + INTERVAL '1 month',
                        updated_at = NOW()
                    WHERE id = '{sub["id"]}'
                """)
                processed += 1
            except Exception:
                failures += 1
        
        return {
            "processed": processed,
            "failures": failures,
            "total_considered": len(result.get("rows", []))
        }

    async def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel existing subscription."""
        await query_db(f"""
            UPDATE subscriptions
            SET status = 'CANCELED',
                canceled_at = NOW(),
                updated_at = NOW()
            WHERE id = '{subscription_id}'
        """)
        return True
