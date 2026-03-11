from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from core.database import query_db

class SubscriptionManager:
    """Handles automated subscription lifecycle management."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
    
    async def create_subscription(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new subscription with automated onboarding."""
        try:
            # Validate required fields
            if not all(k in customer_data for k in ['email', 'payment_method_id', 'plan_id']):
                return {"success": False, "error": "Missing required fields"}
            
            # Create customer record
            customer_id = await self._create_customer(customer_data)
            if not customer_id:
                return {"success": False, "error": "Failed to create customer"}
            
            # Process initial payment
            payment_result = await self._process_payment(
                customer_id,
                customer_data['payment_method_id'],
                customer_data['plan_id']
            )
            
            if not payment_result.get('success'):
                return {"success": False, "error": payment_result.get('error', 'Payment failed')}
            
            # Create subscription record
            sub_id = await self._create_subscription_record(
                customer_id,
                customer_data['plan_id'],
                payment_result['payment_id']
            )
            
            return {
                "success": True,
                "subscription_id": sub_id,
                "customer_id": customer_id,
                "next_billing_date": (datetime.now() + timedelta(days=30)).isoformat()
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _create_customer(self, data: Dict[str, Any]) -> str:
        """Create customer record in database."""
        res = await self.execute_sql(
            f"""
            INSERT INTO customers (
                email, name, billing_address, 
                created_at, updated_at
            ) VALUES (
                '{data['email']}',
                {f"'{data.get('name')}'" if data.get('name') else 'NULL'},
                {f"'{json.dumps(data.get('billing_address', {}))}'" if data.get('billing_address') else 'NULL'},
                NOW(),
                NOW()
            )
            RETURNING id
            """
        )
        return res.get('rows', [{}])[0].get('id')
    
    async def _process_payment(self, customer_id: str, payment_method_id: str, plan_id: str) -> Dict[str, Any]:
        """Process payment via payment processor."""
        # In MVP, we'll just record the payment
        # In production, integrate with Stripe/other processor
        res = await self.execute_sql(
            f"""
            INSERT INTO payments (
                customer_id, amount_cents, currency,
                payment_method_id, status, plan_id
            ) VALUES (
                '{customer_id}',
                1000,  # $10.00 in cents for MVP
                'usd',
                '{payment_method_id}',
                'succeeded',
                '{plan_id}'
            )
            RETURNING id
            """
        )
        return {
            "success": True,
            "payment_id": res.get('rows', [{}])[0].get('id')
        }
    
    async def _create_subscription_record(self, customer_id: str, plan_id: str, payment_id: str) -> str:
        """Create subscription record in database."""
        res = await self.execute_sql(
            f"""
            INSERT INTO subscriptions (
                customer_id, plan_id, status,
                current_period_start, current_period_end,
                latest_payment_id
            ) VALUES (
                '{customer_id}',
                '{plan_id}',
                'active',
                NOW(),
                NOW() + INTERVAL '30 days',
                '{payment_id}'
            )
            RETURNING id
            """
        )
        return res.get('rows', [{}])[0].get('id')
    
    async def process_recurring_billing(self) -> Dict[str, Any]:
        """Process all subscriptions due for renewal."""
        try:
            # Get subscriptions due for renewal
            res = await self.execute_sql(
                """
                SELECT id, customer_id, plan_id 
                FROM subscriptions 
                WHERE status = 'active'
                AND current_period_end <= NOW() + INTERVAL '3 days'
                """
            )
            subs = res.get('rows', [])
            
            processed = 0
            for sub in subs:
                # Process payment
                payment_result = await self._process_payment(
                    sub['customer_id'],
                    f"recurring_{sub['id']}",
                    sub['plan_id']
                )
                
                if payment_result.get('success'):
                    # Update subscription
                    await self.execute_sql(
                        f"""
                        UPDATE subscriptions
                        SET current_period_start = NOW(),
                            current_period_end = NOW() + INTERVAL '30 days',
                            latest_payment_id = '{payment_result['payment_id']}',
                            updated_at = NOW()
                        WHERE id = '{sub['id']}'
                        """
                    )
                    processed += 1
            
            return {
                "success": True,
                "processed": processed,
                "total_due": len(subs)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
