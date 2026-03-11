from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import uuid
import json

from core.database import query_db
from core.payments import create_subscription, charge_customer
from core.onboarding import complete_onboarding

class AutomatedService:
    """Handles automated billing, service delivery and customer onboarding."""

    def __init__(self):
        self.service_name = "automated_revenue_product"
        self.base_price = 9900  # $99/month in cents
        self.trial_days = 7

    async def onboard_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fully automated customer onboarding."""
        # Generate unique customer ID
        customer_id = str(uuid.uuid4())
        
        # Complete onboarding steps
        onboarding_result = await complete_onboarding(
            customer_id=customer_id,
            email=customer_data['email'],
            service_type=self.service_name
        )

        if not onboarding_result.get('success'):
            return {
                "success": False,
                "error": onboarding_result.get('error', 'Onboarding failed')
            }

        # Create payment subscription
        payment_result = await create_subscription(
            customer_id=customer_id,
            email=customer_data['email'],
            amount_cents=self.base_price,
            trial_days=self.trial_days,
            metadata={
                "service": self.service_name,
                "tier": "standard"
            }
        )

        if not payment_result.get('success'):
            return {
                "success": False,
                "error": payment_result.get('error', 'Payment setup failed')
            }

        # Record successful onboarding in revenue system
        await self._record_revenue_event(
            customer_id=customer_id,
            event_type='onboarding',
            amount_cents=0,  # Trial period
            metadata={
                "service": self.service_name,
                "plan": "trial",
                "payment_id": payment_result['payment_id']
            }
        )

        return {
            "success": True,
            "customer_id": customer_id,
            "payment_id": payment_result['payment_id'],
            "trial_ends_at": (datetime.utcnow() + timedelta(days=self.trial_days)).isoformat()
        }

    async def process_monthly_billing(self) -> Dict[str, Any]:
        """Process all recurring monthly charges."""
        # Get all active subscriptions
        result = await query_db(
            f"SELECT customer_id, payment_id FROM subscriptions WHERE service = '{self.service_name}' AND status = 'active'"
        )
        subscribers = result.get('rows', [])

        successful = 0
        failed = 0

        for sub in subscribers:
            customer_id = sub['customer_id']
            payment_id = sub['payment_id']

            # Process monthly charge
            charge_result = await charge_customer(
                payment_id=payment_id,
                amount_cents=self.base_price,
                description=f"{self.service_name} monthly subscription"
            )

            if charge_result.get('success'):
                successful += 1
                await self._record_revenue_event(
                    customer_id=customer_id,
                    event_type='revenue',
                    amount_cents=self.base_price,
                    metadata={
                        "service": self.service_name,
                        "payment_id": payment_id,
                        "billing_cycle": "monthly"
                    }
                )
            else:
                failed += 1
                await self._record_revenue_event(
                    customer_id=customer_id,
                    event_type='billing_failed',
                    amount_cents=0,
                    metadata={
                        "error": charge_result.get('error'),
                        "payment_id": payment_id
                    }
                )

        return {
            "success": True,
            "successful_charges": successful,
            "failed_charges": failed,
            "total_revenue_cents": successful * self.base_price
        }

    async def _record_revenue_event(
        self,
        customer_id: str,
        event_type: str,
        amount_cents: int,
        metadata: Dict[str, Any]
    ) -> None:
        """Record revenue event in tracking system."""
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, customer_id, event_type, amount_cents,
                currency, source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(), '{customer_id}', '{event_type}',
                {amount_cents}, 'USD', '{self.service_name}',
                '{json.dumps(metadata)}', NOW()
            )
            """
        )
