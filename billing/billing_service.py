"""
Automated Billing Service - Handles subscriptions, payments, and revenue tracking.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db

class BillingService:
    """Core billing operations."""
    
    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: str) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            # Create subscription record
            sub_id = "sub_" + str(int(datetime.now().timestamp()))
            await query_db(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status,
                    created_at, updated_at, payment_method
                ) VALUES (
                    '{sub_id}', '{customer_id}', '{plan_id}',
                    'active', NOW(), NOW(), '{payment_method}'
                )
                """
            )
            
            # Log initial payment
            await self._log_revenue_event(
                event_type="revenue",
                amount_cents=1000,  # Example amount
                source="subscription",
                metadata={
                    "subscription_id": sub_id,
                    "plan_id": plan_id,
                    "customer_id": customer_id
                }
            )
            
            return {"success": True, "subscription_id": sub_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def process_payment_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle payment processor webhook."""
        event_type = payload.get("type")
        
        if event_type == "payment.succeeded":
            await self._log_revenue_event(
                event_type="revenue",
                amount_cents=int(float(payload.get("amount", 0)) * 100),
                source="payment",
                metadata=payload
            )
            return {"success": True}
        
        return {"success": False, "error": "Unhandled webhook type"}
    
    async def _log_revenue_event(
        self,
        event_type: str,
        amount_cents: int,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log revenue event to tracking system."""
        metadata_json = json.dumps(metadata or {})
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(), '{event_type}', {amount_cents},
                '{source}', '{metadata_json}'::jsonb, NOW(), NOW()
            )
            """
        )

    async def deliver_service(self, customer_id: str) -> Dict[str, Any]:
        """Automated service delivery."""
        try:
            # Check active subscription
            res = await query_db(
                f"""
                SELECT id FROM subscriptions
                WHERE customer_id = '{customer_id}'
                AND status = 'active'
                LIMIT 1
                """
            )
            if not res.get("rows"):
                return {"success": False, "error": "No active subscription"}
            
            # Perform service delivery
            # (Add your specific service delivery logic here)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
