"""
Billing system for handling subscriptions, invoices, and revenue recognition.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

from core.database import query_db
from payment_processor import PaymentProcessor

logger = logging.getLogger(__name__)

class BillingManager:
    def __init__(self):
        self.processor = PaymentProcessor()

    async def create_billing_account(self, user_id: str, email: str, name: str) -> Dict:
        """Create a new billing account with payment processor."""
        try:
            # Create Stripe customer
            customer_res = await self.processor.create_customer(email, name)
            if not customer_res["success"]:
                return customer_res

            # Store in database
            await query_db(
                f"""
                INSERT INTO billing_accounts (
                    user_id, 
                    customer_id,
                    email,
                    created_at,
                    updated_at
                ) VALUES (
                    '{user_id}',
                    '{customer_res["customer_id"]}',
                    '{email}',
                    NOW(),
                    NOW()
                )
                """
            )
            return {"success": True, "customer_id": customer_res["customer_id"]}
        except Exception as e:
            logger.error(f"Failed to create billing account: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_subscription(
        self,
        user_id: str,
        price_id: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create a new subscription for a user."""
        try:
            # Get customer ID
            account = await query_db(
                f"SELECT customer_id FROM billing_accounts WHERE user_id = '{user_id}' LIMIT 1"
            )
            if not account.get("rows"):
                return {"success": False, "error": "Billing account not found"}

            customer_id = account["rows"][0]["customer_id"]
            
            # Create subscription
            sub_res = await self.processor.create_subscription(
                customer_id,
                price_id,
                metadata
            )
            if not sub_res["success"]:
                return sub_res

            # Store subscription in database
            await query_db(
                f"""
                INSERT INTO subscriptions (
                    user_id,
                    subscription_id,
                    price_id,
                    status,
                    created_at,
                    updated_at,
                    metadata
                ) VALUES (
                    '{user_id}',
                    '{sub_res["subscription_id"]}',
                    '{price_id}',
                    'pending',
                    NOW(),
                    NOW(),
                    '{json.dumps(metadata or {})}'
                )
                """
            )
            return sub_res
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}

    async def record_payment_event(
        self,
        event_type: str,
        amount: float,
        currency: str,
        payment_id: str,
        customer_id: str,
        subscription_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Record a payment event in the revenue system."""
        try:
            await query_db(
                f"""
                INSERT INTO revenue_events (
                    event_type,
                    amount_cents,
                    currency,
                    source,
                    recorded_at,
                    created_at,
                    metadata,
                    attribution
                ) VALUES (
                    'revenue',
                    {int(amount * 100)},
                    '{currency}',
                    'stripe',
                    NOW(),
                    NOW(),
                    '{json.dumps(metadata or {})}',
                    jsonb_build_object(
                        'payment_id', '{payment_id}',
                        'customer_id', '{customer_id}',
                        'subscription_id', {f"'{subscription_id}'" if subscription_id else 'NULL'}
                    )
                )
                """
            )
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to record payment: {str(e)}")
            return {"success": False, "error": str(e)}
