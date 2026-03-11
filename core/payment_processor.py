import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from core.database import execute_sql

logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Handles payment processing and transaction logging."""
    
    def __init__(self):
        self.currency = "USD"  # Default currency
        
    async def process_payment(self, amount_cents: int, source: str, metadata: Optional[Dict] = None) -> Dict:
        """
        Process a payment and log the transaction.
        
        Args:
            amount_cents: Amount in cents
            source: Payment source identifier
            metadata: Additional transaction metadata
            
        Returns:
            Dict with success status and transaction details
        """
        try:
            # Validate input
            if not isinstance(amount_cents, int) or amount_cents <= 0:
                raise ValueError("Invalid amount")
                
            if not source:
                raise ValueError("Source is required")
                
            # Prepare transaction data
            transaction_data = {
                "event_type": "revenue",
                "amount_cents": amount_cents,
                "currency": self.currency,
                "source": source,
                "metadata": metadata or {},
                "recorded_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Insert transaction
            sql = """
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                %(event_type)s,
                %(amount_cents)s,
                %(currency)s,
                %(source)s,
                %(metadata)s,
                %(recorded_at)s,
                NOW()
            )
            RETURNING id
            """
            
            result = await execute_sql(sql, transaction_data)
            transaction_id = result["rows"][0]["id"]
            
            logger.info(f"Successfully processed payment: {transaction_id}")
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "amount_cents": amount_cents,
                "currency": self.currency
            }
            
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
