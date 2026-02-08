"""
Automated Billing System - Handles subscriptions, payments, and revenue tracking.

Features:
- Subscription lifecycle management
- Payment processing integration
- Automated dunning and retries
- Revenue recognition
- Tax compliance
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

class AutomatedBilling:
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: str) -> Dict[str, Any]:
        """Create new subscription with initial payment"""
        try:
            # Create subscription record
            sub_id = await self.execute_sql(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status, 
                    start_date, end_date, payment_method,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{plan_id}',
                    'active',
                    NOW(),
                    NOW() + INTERVAL '1 month',
                    '{payment_method}',
                    NOW(),
                    NOW()
                )
                RETURNING id
                """
            )
            
            # Process initial payment
            payment_result = await self.process_payment(customer_id, payment_method, plan_id)
            
            if not payment_result.get("success"):
                await self.execute_sql(
                    f"UPDATE subscriptions SET status = 'failed' WHERE id = '{sub_id}'"
                )
                return {"success": False, "error": "Payment failed"}
                
            return {"success": True, "subscription_id": sub_id}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def process_payment(self, customer_id: str, payment_method: str, amount: float) -> Dict[str, Any]:
        """Process payment through payment gateway"""
        try:
            # Integration with payment processor
            payment_result = await self._call_payment_gateway({
                "customer_id": customer_id,
                "payment_method": payment_method,
                "amount": amount
            })
            
            if payment_result.get("status") != "succeeded":
                return {"success": False, "error": "Payment declined"}
                
            # Record payment
            await self.execute_sql(
                f"""
                INSERT INTO payments (
                    id, customer_id, amount, currency,
                    payment_method, status, gateway_response,
                    created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    {amount},
                    'USD',
                    '{payment_method}',
                    'succeeded',
                    '{json.dumps(payment_result)}',
                    NOW()
                )
                """
            )
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def _call_payment_gateway(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock payment gateway integration"""
        # In production this would call Stripe, PayPal, etc.
        return {"status": "succeeded", "transaction_id": "txn_123"}
        
    async def handle_recurring_billing(self) -> Dict[str, Any]:
        """Process all due subscriptions"""
        try:
            # Get subscriptions due for renewal
            subscriptions = await self.execute_sql(
                """
                SELECT id, customer_id, plan_id, payment_method
                FROM subscriptions
                WHERE status = 'active'
                  AND end_date <= NOW()
                LIMIT 1000
                """
            )
            
            processed = 0
            failures = []
            
            for sub in subscriptions.get("rows", []):
                payment_result = await self.process_payment(
                    sub["customer_id"],
                    sub["payment_method"],
                    sub["plan_id"]
                )
                
                if payment_result.get("success"):
                    # Extend subscription
                    await self.execute_sql(
                        f"""
                        UPDATE subscriptions
                        SET end_date = NOW() + INTERVAL '1 month',
                            updated_at = NOW()
                        WHERE id = '{sub["id"]}'
                        """
                    )
                    processed += 1
                else:
                    # Handle failed payment
                    await self.handle_payment_failure(sub["id"])
                    failures.append({
                        "subscription_id": sub["id"],
                        "error": payment_result.get("error")
                    })
                    
            return {
                "success": True,
                "processed": processed,
                "failures": failures
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def handle_payment_failure(self, subscription_id: str) -> Dict[str, Any]:
        """Handle failed payment with retry logic"""
        try:
            # Get failure count
            failure_count = await self.execute_sql(
                f"""
                SELECT COUNT(*) as count
                FROM payment_failures
                WHERE subscription_id = '{subscription_id}'
                """
            )
            
            failures = failure_count.get("rows", [{}])[0].get("count", 0)
            
            if failures >= 3:
                # Cancel subscription after 3 failed attempts
                await self.execute_sql(
                    f"""
                    UPDATE subscriptions
                    SET status = 'canceled',
                        updated_at = NOW()
                    WHERE id = '{subscription_id}'
                    """
                )
            else:
                # Schedule retry
                await self.execute_sql(
                    f"""
                    INSERT INTO payment_failures (
                        id, subscription_id, retry_at,
                        created_at
                    ) VALUES (
                        gen_random_uuid(),
                        '{subscription_id}',
                        NOW() + INTERVAL '3 days',
                        NOW()
                    )
                    """
                )
                
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
