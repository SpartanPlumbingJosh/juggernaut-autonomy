"""
Billing Service - Handles subscriptions, invoices and payments.
Integrates with payment processors and revenue tracking.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
import json
import logging

from core.database import query_db

logger = logging.getLogger(__name__)

class BillingService:
    def __init__(self, db_executor):
        self.db_executor = db_executor

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method_id: str) -> Dict[str, Any]:
        """Create a new subscription for a customer."""
        try:
            # Generate subscription data
            subscription_id = f"sub_{datetime.now(timezone.utc).timestamp()}"
            start_date = datetime.now(timezone.utc)
            
            # Store subscription in database
            await self.db_executor(f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, 
                    status, start_date, payment_method_id
                ) VALUES (
                    '{subscription_id}',
                    '{customer_id}',
                    '{plan_id}',
                    'active',
                    '{start_date.isoformat()}',
                    '{payment_method_id}'
                )
            """)
            
            return {
                "success": True,
                "subscription_id": subscription_id,
                "start_date": start_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}

    async def record_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record a payment in the revenue tracking system."""
        try:
            amount_cents = int(float(payment_data.get("amount", 0)) * 100)
            currency = payment_data.get("currency", "usd").lower()
            
            await self.db_executor(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {amount_cents},
                    '{currency}',
                    'payment_processor',
                    '{json.dumps(payment_data)}'::jsonb,
                    NOW()
                )
            """)
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Failed to record payment: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process webhook events from payment processor."""
        try:
            if event_type == "payment_succeeded":
                return await self.record_payment(data)
            elif event_type == "subscription_created":
                return await self.create_subscription(
                    data.get("customer_id"),
                    data.get("plan_id"),
                    data.get("payment_method_id")
                )
            else:
                return {"success": False, "error": "Unsupported event type"}
                
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
