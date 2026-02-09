"""
Core billing and subscription management service.
Handles recurring payments, invoicing, and account status.
"""
import datetime
from datetime import timezone
import json
from typing import Dict, List, Optional

from core.database import query_db


class BillingService:
    """Main billing operations."""
    
    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: Optional[Dict] = None) -> Dict:
        """Initialize a new subscription with trial period."""
        try:
            # Validate plan exists
            plan = await query_db(
                f"SELECT * FROM billing_plans WHERE id = '{plan_id}' AND status = 'active'"
            )
            if not plan.get('rows'):
                return {"success": False, "error": "Invalid plan"}

            # Create billing agreement
            now = datetime.datetime.now(timezone.utc)
            trial_end = now + datetime.timedelta(days=7)  # Default trial period
            subscription_id = await query_db(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status,
                    current_period_start, current_period_end,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{plan_id}',
                    'trialing',
                    '{now.isoformat()}',
                    '{trial_end.isoformat()}',
                    NOW(),
                    NOW()
                )
                RETURNING id
                """
            )
            
            # Initialize billing events
            await query_db(
                f"""
                INSERT INTO billing_events (
                    subscription_id, type, amount_cents,
                    status, created_at
                ) VALUES (
                    '{subscription_id}',
                    'subscription_created',
                    0,
                    'complete',
                    NOW()
                )
                """
            )
            
            return {"success": True, "subscription_id": subscription_id}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def process_payment(self, subscription_id: str, amount_cents: int) -> Dict:
        """Process recurring or one-time payment."""
        try:
            # Get current subscription status
            sub = await query_db(
                f"SELECT * FROM subscriptions WHERE id = '{subscription_id}'"
            )
            if not sub.get('rows'):
                return {"success": False, "error": "Invalid subscription"}
            
            # Create payment record
            payment = await query_db(
                f"""
                INSERT INTO payments (
                    id, subscription_id, amount_cents,
                    status, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{subscription_id}',
                    {amount_cents},
                    'processing',
                    NOW()
                )
                RETURNING id
                """
            )
            
            # Simulate payment gateway response
            await query_db(
                f"""
                UPDATE payments 
                SET status = 'completed', 
                    processed_at = NOW()
                WHERE id = '{payment['id']}'
                """
            )
            
            # Record revenue event
            await query_db(
                f"""
                INSERT INTO revenue_events (
                    event_type, amount_cents, 
                    recorded_at, metadata
                ) VALUES (
                    'revenue',
                    {amount_cents},
                    NOW(),
                    '{{"type":"recurring","subscription_id":"{subscription_id}"}}'::jsonb
                )
                """
            )
            
            return {"success": True, "payment_id": payment['id']}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_subscription_status(self, subscription_id: str) -> Dict:
        """Retrieve current subscription details."""
        subscription = await query_db(
            f"""
            SELECT s.*, p.name as plan_name, p.amount_cents as plan_amount
            FROM subscriptions s
            JOIN billing_plans p ON s.plan_id = p.id 
            WHERE s.id = '{subscription_id}'
            """
        )
        return subscription.get('rows', [{}])[0] or {}
