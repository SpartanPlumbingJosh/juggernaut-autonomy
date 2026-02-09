"""
Billing Service - Handles payment processing, subscriptions, and invoicing.
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.database import query_db
from core.payment_providers import PaymentProvider

class BillingService:
    def __init__(self):
        self.payment_provider = PaymentProvider()

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: str) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            # Create subscription with payment provider
            subscription = await self.payment_provider.create_subscription(
                customer_id=customer_id,
                plan_id=plan_id,
                payment_method=payment_method
            )
            
            # Store subscription in database
            await query_db(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status, 
                    start_date, end_date, payment_method
                ) VALUES (
                    '{subscription['id']}',
                    '{customer_id}',
                    '{plan_id}',
                    'active',
                    NOW(),
                    NOW() + INTERVAL '1 year',
                    '{payment_method}'
                )
                """
            )
            
            return {"success": True, "subscription": subscription}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def process_payment(self, amount: float, currency: str, customer_id: str) -> Dict[str, Any]:
        """Process a payment."""
        try:
            # Process payment with provider
            payment = await self.payment_provider.process_payment(
                amount=amount,
                currency=currency,
                customer_id=customer_id
            )
            
            # Record revenue event
            await self._record_revenue_event(
                event_type="payment",
                amount=amount,
                currency=currency,
                customer_id=customer_id,
                payment_id=payment['id']
            )
            
            return {"success": True, "payment": payment}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _record_revenue_event(self, event_type: str, amount: float, currency: str, 
                                  customer_id: str, payment_id: str) -> None:
        """Record a revenue event."""
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                customer_id, payment_id, recorded_at
            ) VALUES (
                gen_random_uuid(),
                '{event_type}',
                {int(amount * 100)},
                '{currency}',
                '{customer_id}',
                '{payment_id}',
                NOW()
            )
            """
        )

    async def generate_invoice(self, subscription_id: str) -> Dict[str, Any]:
        """Generate an invoice for a subscription."""
        try:
            # Get subscription details
            subscription = await query_db(
                f"""
                SELECT * FROM subscriptions
                WHERE id = '{subscription_id}'
                LIMIT 1
                """
            )
            
            if not subscription.get('rows'):
                return {"success": False, "error": "Subscription not found"}
            
            # Generate invoice
            invoice = await self.payment_provider.generate_invoice(
                subscription_id=subscription_id
            )
            
            return {"success": True, "invoice": invoice}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def recognize_revenue(self) -> Dict[str, Any]:
        """Run revenue recognition for all pending transactions."""
        try:
            # Get unrecognized revenue events
            events = await query_db(
                """
                SELECT * FROM revenue_events
                WHERE recognized_at IS NULL
                ORDER BY recorded_at ASC
                """
            )
            
            recognized = 0
            for event in events.get('rows', []):
                # Apply revenue recognition logic
                await self._apply_revenue_recognition(event)
                recognized += 1
                
            return {"success": True, "recognized": recognized}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _apply_revenue_recognition(self, event: Dict[str, Any]) -> None:
        """Apply revenue recognition rules to an event."""
        # Example recognition logic - could be more complex based on business rules
        await query_db(
            f"""
            UPDATE revenue_events
            SET recognized_at = NOW()
            WHERE id = '{event['id']}'
            """
        )
