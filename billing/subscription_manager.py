from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from core.database import query_db

class SubscriptionManager:
    async def create_subscription(self, customer_id: str, plan_id: str, trial_days: int = 0) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            # Get plan details
            plan = await query_db(f"SELECT * FROM billing_plans WHERE id = '{plan_id}'")
            if not plan.get("rows"):
                return {"success": False, "error": "Plan not found"}
            
            plan_data = plan["rows"][0]
            
            # Calculate dates
            now = datetime.now(timezone.utc)
            start_date = now
            end_date = now + timedelta(days=plan_data["billing_interval_days"])
            
            if trial_days > 0:
                start_date = now + timedelta(days=trial_days)
                end_date = start_date + timedelta(days=plan_data["billing_interval_days"])
            
            # Create subscription
            await query_db(f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status,
                    start_date, end_date, trial_end,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), '{customer_id}', '{plan_id}', 'active',
                    '{start_date.isoformat()}', '{end_date.isoformat()}',
                    {'NULL' if trial_days == 0 else f"'{start_date.isoformat()}'"},
                    NOW(), NOW()
                )
            """)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def process_renewals(self) -> Dict[str, Any]:
        """Process subscriptions due for renewal."""
        try:
            # Get subscriptions due for renewal
            subscriptions = await query_db("""
                SELECT * FROM subscriptions
                WHERE end_date <= NOW()
                AND status = 'active'
                FOR UPDATE
            """)
            
            renewed = 0
            failures = []
            
            for sub in subscriptions.get("rows", []):
                try:
                    # Get plan details
                    plan = await query_db(f"SELECT * FROM billing_plans WHERE id = '{sub['plan_id']}'")
                    if not plan.get("rows"):
                        failures.append({"subscription_id": sub["id"], "error": "Plan not found"})
                        continue
                    
                    plan_data = plan["rows"][0]
                    
                    # Calculate new end date
                    new_end_date = datetime.now(timezone.utc) + timedelta(days=plan_data["billing_interval_days"])
                    
                    # Update subscription
                    await query_db(f"""
                        UPDATE subscriptions
                        SET end_date = '{new_end_date.isoformat()}',
                            updated_at = NOW()
                        WHERE id = '{sub['id']}'
                    """)
                    
                    renewed += 1
                except Exception as e:
                    failures.append({"subscription_id": sub["id"], "error": str(e)})
            
            return {
                "success": True,
                "renewed": renewed,
                "failures": failures
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def generate_invoices(self) -> Dict[str, Any]:
        """Generate invoices for subscriptions."""
        try:
            # Get subscriptions needing invoices
            subscriptions = await query_db("""
                SELECT s.*, p.price_cents, p.currency
                FROM subscriptions s
                JOIN billing_plans p ON s.plan_id = p.id
                WHERE s.end_date <= NOW()
                AND s.status = 'active'
                AND NOT EXISTS (
                    SELECT 1 FROM invoices i
                    WHERE i.subscription_id = s.id
                    AND i.period_end = s.end_date
                )
            """)
            
            generated = 0
            failures = []
            
            for sub in subscriptions.get("rows", []):
                try:
                    await query_db(f"""
                        INSERT INTO invoices (
                            id, subscription_id, amount_cents, currency,
                            period_start, period_end, status,
                            created_at, updated_at
                        ) VALUES (
                            gen_random_uuid(), '{sub['id']}', {sub['price_cents']},
                            '{sub['currency']}', '{sub['start_date']}',
                            '{sub['end_date']}', 'pending',
                            NOW(), NOW()
                        )
                    """)
                    generated += 1
                except Exception as e:
                    failures.append({"subscription_id": sub["id"], "error": str(e)})
            
            return {
                "success": True,
                "generated": generated,
                "failures": failures
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
