from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional
import uuid
import json

class BillingManager:
    """Handles subscription billing and payment processing."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action

    def create_subscription(self, customer_id: str, plan_id: str, payment_token: str) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            # Validate plan
            if plan_id not in PLANS:
                return {"success": False, "error": "Invalid plan"}
            
            plan = PLANS[plan_id]
            
            # Create subscription record
            sub_id = str(uuid.uuid4())
            now = datetime.utcnow()
            next_billing = now + timedelta(days=30) if plan["interval"] == "month" else now + timedelta(days=365)
            
            self.execute_sql(f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status, 
                    current_period_start, current_period_end,
                    created_at, updated_at
                ) VALUES (
                    '{sub_id}', '{customer_id}', '{plan_id}', 'active',
                    '{now.isoformat()}', '{next_billing.isoformat()}',
                    NOW(), NOW()
                )
            """)
            
            # Record initial payment
            self.record_payment(sub_id, plan["price_cents"], payment_token)
            
            return {"success": True, "subscription_id": sub_id}
            
        except Exception as e:
            self.log_action("billing.error", f"Failed to create subscription: {str(e)}", level="error")
            return {"success": False, "error": str(e)}

    def record_payment(self, subscription_id: str, amount_cents: int, payment_token: str) -> Dict[str, Any]:
        """Record a payment transaction."""
        try:
            payment_id = str(uuid.uuid4())
            
            self.execute_sql(f"""
                INSERT INTO payments (
                    id, subscription_id, amount_cents, currency,
                    status, payment_token, created_at
                ) VALUES (
                    '{payment_id}', '{subscription_id}', {amount_cents}, 'usd',
                    'pending', '{payment_token}', NOW()
                )
            """)
            
            # Process payment (integration with payment gateway would go here)
            # For MVP, we'll just mark as succeeded
            self.execute_sql(f"""
                UPDATE payments
                SET status = 'succeeded',
                    processed_at = NOW()
                WHERE id = '{payment_id}'
            """)
            
            return {"success": True, "payment_id": payment_id}
            
        except Exception as e:
            self.log_action("billing.error", f"Failed to record payment: {str(e)}", level="error")
            return {"success": False, "error": str(e)}

    def track_usage(self, customer_id: str, usage_type: str, quantity: int) -> Dict[str, Any]:
        """Track customer usage for billing purposes."""
        try:
            usage_id = str(uuid.uuid4())
            
            self.execute_sql(f"""
                INSERT INTO usage_records (
                    id, customer_id, usage_type, quantity,
                    recorded_at, created_at
                ) VALUES (
                    '{usage_id}', '{customer_id}', '{usage_type}', {quantity},
                    NOW(), NOW()
                )
            """)
            
            return {"success": True}
            
        except Exception as e:
            self.log_action("billing.error", f"Failed to track usage: {str(e)}", level="error")
            return {"success": False, "error": str(e)}

    def check_usage_limits(self, customer_id: str) -> Dict[str, Any]:
        """Check if customer has exceeded usage limits."""
        try:
            # Get current subscription
            sub_res = self.execute_sql(f"""
                SELECT plan_id, current_period_start
                FROM subscriptions
                WHERE customer_id = '{customer_id}'
                AND status = 'active'
                LIMIT 1
            """)
            
            if not sub_res.get("rows"):
                return {"success": False, "error": "No active subscription"}
            
            sub = sub_res["rows"][0]
            plan = PLANS[sub["plan_id"]]
            
            # Get current usage
            usage_res = self.execute_sql(f"""
                SELECT usage_type, SUM(quantity) as total
                FROM usage_records
                WHERE customer_id = '{customer_id}'
                AND recorded_at >= '{sub["current_period_start"]}'
                GROUP BY usage_type
            """)
            
            usage = {row["usage_type"]: row["total"] for row in usage_res.get("rows", [])}
            
            # Check limits
            limits = plan["usage_limits"]
            exceeded = {
                "api_calls": usage.get("api_calls", 0) >= limits["api_calls"],
                "storage_mb": usage.get("storage_mb", 0) >= limits["storage_mb"]
            }
            
            return {
                "success": True,
                "limits": limits,
                "usage": usage,
                "exceeded": exceeded
            }
            
        except Exception as e:
            self.log_action("billing.error", f"Failed to check usage limits: {str(e)}", level="error")
            return {"success": False, "error": str(e)}
