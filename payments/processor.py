"""Core payment processing and revenue tracking logic."""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Handle payment processing and revenue tracking."""

    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql

    def process_payment(
        self,
        amount: Decimal,
        currency: str,
        source: str,
        customer_id: str,
        product_details: Dict,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, str]:
        """Process a payment and record revenue event.
        
        Returns:
            Tuple of (success, transaction_id)
        """
        metadata = metadata or {}
        transaction_id = None

        try:
            # Process transaction via Stripe/PayPal API would go here
            # For MVP we'll simulate successful processing
            
            # Record revenue event
            transaction_id = self._record_revenue_event(
                amount=amount,
                currency=currency,
                source=source,
                customer_id=customer_id,
                product_details=product_details,
                metadata=metadata
            )
            
            # Trigger fulfillment would go here
            self._trigger_fulfillment(transaction_id, product_details)
            
            return (True, transaction_id)

        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            self._record_failed_payment(
                amount=amount,
                currency=currency,
                source=source,
                error=str(e),
                metadata=metadata
            )
            return (False, str(e))

    def _record_revenue_event(
        self,
        amount: Decimal,
        currency: str,
        source: str,
        customer_id: str,
        product_details: Dict,
        metadata: Dict
    ) -> str:
        """Record successful revenue event in database."""
        amount_cents = int(amount * 100)
        
        result = self.execute_sql(
            f"""
            INSERT INTO revenue_events (
                id, 
                event_type,
                amount_cents,
                currency,
                source,
                customer_id,
                product_details,
                metadata,
                recorded_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                '{currency}',
                '{source}',
                '{customer_id}',
                '{json.dumps(product_details)}',
                '{json.dumps(metadata)}',
                NOW()
            )
            RETURNING id
            """
        )
        
        if not result or not result.get('rows'):
            raise Exception("Failed to record revenue event")
            
        return result['rows'][0]['id']

    def _record_failed_payment(
        self,
        amount: Decimal,
        currency: str,
        source: str,
        error: str,
        metadata: Dict
    ) -> None:
        """Record payment failure for analytics."""
        amount_cents = int(amount * 100)
        
        metadata['error'] = error
        self.execute_sql(
            f"""
            INSERT INTO revenue_events (
                id, 
                event_type,
                amount_cents,
                currency,
                source,
                metadata,
                recorded_at
            ) VALUES (
                gen_random_uuid(),
                'failed_payment',
                {amount_cents},
                '{currency}',
                '{source}',
                '{json.dumps(metadata)}',
                NOW()
            )
            """
        )

    def _trigger_fulfillment(self, transaction_id: str, product_details: Dict):
        """Trigger product/service fulfillment."""
        # MVP just logs - would integrate with email/delivery systems
        logger.info(f"Fulfillment triggered for transaction {transaction_id}")
