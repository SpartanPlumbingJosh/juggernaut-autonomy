from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from core.payment_gateway import PaymentGateway

class BillingService:
    """Handle all billing logic and subscription management."""
    
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql
        self.payment_gateway = PaymentGateway()
    
    async def create_customer(
        self,
        email: str,
        name: str,
        payment_method: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create new billing customer."""
        # Create in payment gateway
        result = await self.payment_gateway.create_customer(email, name, metadata)
        if not result['success']:
            return result
            
        customer_id = result['customer_id']
        
        # Store in database
        try:
            await self.execute_sql(
                f"""
                INSERT INTO customers (
                    id, email, name, payment_gateway_id,
                    created_at, updated_at, metadata
                ) VALUES (
                    gen_random_uuid(),
                    '{email}',
                    '{name}',
                    '{customer_id}',
                    NOW(),
                    NOW(),
                    '{json.dumps(metadata or {})}'::jsonb
                )
                RETURNING id
                """
            )
            return {"success": True, "customer_id": customer_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        trial_days: int = 0
    ) -> Dict:
        """Create new subscription for customer."""
        # Get plan details
        plan = await self._get_plan(plan_id)
        if not plan:
            return {"success": False, "error": "Invalid plan"}
            
        # Create in payment gateway
        result = await self.payment_gateway.create_subscription(
            customer_id,
            plan['price_id'],
            trial_days
        )
        if not result['success']:
            return result
            
        # Store in database
        try:
            await self.execute_sql(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status,
                    current_period_end, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{plan_id}',
                    '{result['status']}',
                    to_timestamp({result['current_period_end']}),
                    NOW(),
                    NOW()
                )
                RETURNING id
                """
            )
            return {"success": True, "subscription_id": result['subscription_id']}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_plan(self, plan_id: str) -> Optional[Dict]:
        """Get pricing plan details."""
        try:
            res = await self.execute_sql(
                f"SELECT * FROM billing_plans WHERE id = '{plan_id}' LIMIT 1"
            )
            return res.get('rows', [{}])[0]
        except Exception:
            return None
    
    async def process_recurring_billing(self) -> Dict:
        """Process all recurring subscriptions due for billing."""
        try:
            # Get subscriptions due for renewal
            res = await self.execute_sql(
                """
                SELECT s.id, s.customer_id, s.plan_id, c.payment_gateway_id
                FROM subscriptions s
                JOIN customers c ON s.customer_id = c.id
                WHERE s.status = 'active'
                  AND s.current_period_end <= NOW() + INTERVAL '3 days'
                LIMIT 100
                """
            )
            subscriptions = res.get('rows', [])
            
            processed = 0
            for sub in subscriptions:
                # Payment will be handled via Stripe webhook
                processed += 1
                
            return {
                "success": True,
                "processed": processed,
                "total": len(subscriptions)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
