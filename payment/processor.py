import logging
from datetime import datetime, timezone
from typing import Dict, Optional

import stripe  # type: ignore

from core.database import execute_sql

logger = logging.getLogger(__name__)


class PaymentProcessor:
    def __init__(self, api_key: str):
        self.stripe = stripe
        self.stripe.api_key = api_key

    async def process_payment(
        self,
        amount_cents: int,
        currency: str,
        source: str,
        metadata: Optional[Dict] = None,
        experiment_id: Optional[str] = None
    ) -> Dict:
        """
        Process payment and log transaction to database.
        Returns dictionary with payment status and details.
        """
        try:
            # Create Stripe charge
            charge = self.stripe.Charge.create(
                amount=amount_cents,
                currency=currency.lower(),
                source=source,
                metadata=metadata or {},
                description=f"Revenue experiment: {experiment_id}" if experiment_id else None
            )

            # Log successful transaction
            await self._log_transaction(
                event_type="revenue",
                amount_cents=amount_cents,
                currency=currency,
                source=source,
                metadata={
                    **(metadata or {}),
                    "payment_processor": "stripe",
                    "charge_id": charge.id,
                    "status": charge.status
                },
                experiment_id=experiment_id
            )

            return {
                "success": True,
                "charge_id": charge.id,
                "amount_cents": amount_cents,
                "currency": currency
            }

        except self.stripe.error.StripeError as e:
            logger.error(f"Payment processing failed: {str(e)}")
            
            # Log failed transaction for auditing
            await self._log_transaction(
                event_type="revenue_attempt",
                amount_cents=amount_cents,
                currency=currency,
                source=source,
                metadata={
                    **(metadata or {}),
                    "payment_processor": "stripe",
                    "error": str(e),
                    "status": "failed"
                },
                experiment_id=experiment_id
            )

            return {
                "success": False,
                "error": str(e),
                "error_type": "payment_error"
            }

    async def _log_transaction(
        self,
        event_type: str,
        amount_cents: int,
        currency: str,
        source: str,
        metadata: Dict,
        experiment_id: Optional[str] = None
    ) -> None:
        """Log transaction to database with automatic retry logic."""
        try:
            metadata_json = json.dumps(metadata)
            recorded_at = datetime.now(timezone.utc).isoformat()

            sql = f"""
            INSERT INTO revenue_events (
                id,
                experiment_id,
                event_type,
                amount_cents,
                currency,
                source,
                metadata,
                recorded_at
            ) VALUES (
                gen_random_uuid(),
                {f"'{experiment_id}'" if experiment_id else "NULL"},
                '{event_type}',
                {amount_cents},
                '{currency}',
                '{source}',
                '{metadata_json}'::jsonb,
                '{recorded_at}'
            )
            """
            
            await execute_sql(sql)
            logger.info(f"Logged {event_type} transaction for {amount_cents} {currency}")
            
        except Exception as e:
            logger.error(f"Failed to log transaction: {str(e)}")
            # TODO: Add dead letter queue for failed transaction logs
