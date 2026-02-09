"""
Payment Processor - Handles revenue transactions and logging.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db


class PaymentProcessor:
    """Process payments and log revenue transactions."""
    
    def __init__(self):
        self.retry_count = 3
    
    async def process_payment(
        self,
        amount_cents: int,
        currency: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
        experiment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a payment and log the transaction."""
        transaction_id = str(uuid.uuid4())
        metadata = metadata or {}
        
        # Build attribution data
        attribution = {}
        if experiment_id:
            attribution["experiment_id"] = experiment_id
        
        # Log the transaction
        try:
            await self._log_transaction(
                transaction_id=transaction_id,
                event_type="revenue",
                amount_cents=amount_cents,
                currency=currency,
                source=source,
                metadata=metadata,
                attribution=attribution
            )
            return {"success": True, "transaction_id": transaction_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def log_cost(
        self,
        amount_cents: int,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
        experiment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Log a cost transaction."""
        transaction_id = str(uuid.uuid4())
        metadata = metadata or {}
        
        # Build attribution data
        attribution = {}
        if experiment_id:
            attribution["experiment_id"] = experiment_id
        
        try:
            await self._log_transaction(
                transaction_id=transaction_id,
                event_type="cost",
                amount_cents=amount_cents,
                currency="USD",  # Costs are always in USD
                source=source,
                metadata=metadata,
                attribution=attribution
            )
            return {"success": True, "transaction_id": transaction_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _log_transaction(
        self,
        transaction_id: str,
        event_type: str,
        amount_cents: int,
        currency: str,
        source: str,
        metadata: Dict[str, Any],
        attribution: Dict[str, Any]
    ) -> None:
        """Internal method to log transaction to database with retries."""
        sql = """
        INSERT INTO revenue_events (
            id,
            event_type,
            amount_cents,
            currency,
            source,
            metadata,
            attribution,
            recorded_at,
            created_at
        ) VALUES (
            %(id)s,
            %(event_type)s,
            %(amount_cents)s,
            %(currency)s,
            %(source)s,
            %(metadata)s,
            %(attribution)s,
            %(recorded_at)s,
            %(created_at)s
        )
        """
        
        params = {
            "id": transaction_id,
            "event_type": event_type,
            "amount_cents": amount_cents,
            "currency": currency,
            "source": source,
            "metadata": json.dumps(metadata),
            "attribution": json.dumps(attribution),
            "recorded_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        }
        
        # Retry logic for database operations
        last_error = None
        for attempt in range(self.retry_count):
            try:
                await query_db(sql, params)
                return
            except Exception as e:
                last_error = e
                continue
        
        raise Exception(f"Failed to log transaction after {self.retry_count} attempts: {str(last_error)}")


# Global instance for easy access
payment_processor = PaymentProcessor()
