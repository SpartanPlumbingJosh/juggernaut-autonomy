"""
Automated revenue transaction processing system.
Handles validation, logging, and error recovery.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Union

from core.database import query_db

logger = logging.getLogger(__name__)

class RevenueProcessor:
    """Process and log revenue transactions automatically."""
    
    def __init__(self):
        self.min_amount = 1  # Minimum transaction amount in cents
        self.max_amount = 1000000  # Maximum transaction amount in cents
        self.valid_currencies = {"USD", "EUR", "GBP"}
        self.valid_event_types = {"revenue", "cost", "refund"}

    async def process_transaction(
        self,
        event_type: str,
        amount_cents: int,
        currency: str,
        source: str,
        metadata: Optional[Dict] = None,
        attribution: Optional[Dict] = None
    ) -> Dict[str, Union[bool, str]]:
        """Process and log a revenue transaction."""
        
        try:
            # Validate inputs
            if event_type not in self.valid_event_types:
                raise ValueError(f"Invalid event_type: {event_type}")
            
            if not isinstance(amount_cents, int) or not (self.min_amount <= amount_cents <= self.max_amount):
                raise ValueError(f"Amount must be integer between {self.min_amount} and {self.max_amount} cents")
                
            if currency not in self.valid_currencies:
                raise ValueError(f"Unsupported currency: {currency}")
                
            if not source or not isinstance(source, str):
                raise ValueError("Source is required and must be string")
                
            # Prepare data for DB
            metadata_json = json.dumps(metadata or {})
            attribution_json = json.dumps(attribution or {})
            recorded_at = datetime.now(timezone.utc).isoformat()
            
            # Insert transaction
            sql = f"""
            INSERT INTO revenue_events (
                event_type,
                amount_cents,
                currency,
                source,
                metadata,
                attribution,
                recorded_at,
                created_at
            ) VALUES (
                '{event_type}',
                {amount_cents},
                '{currency}',
                '{source.replace("'", "''")}',
                '{metadata_json.replace("'", "''")}'::jsonb,
                '{attribution_json.replace("'", "''")}'::jsonb,
                '{recorded_at}',
                NOW()
            )
            RETURNING id
            """
            
            result = await query_db(sql)
            if not result.get("rows"):
                raise RuntimeError("Failed to insert transaction")
                
            return {
                "success": True,
                "transaction_id": result["rows"][0]["id"]
            }
            
        except Exception as e:
            logger.error(f"Transaction processing failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def process_batch(self, transactions: list) -> Dict[str, Union[int, list]]:
        """Process multiple transactions with rollback on failure."""
        success_count = 0
        errors = []
        
        for tx in transactions:
            try:
                result = await self.process_transaction(**tx)
                if result["success"]:
                    success_count += 1
                else:
                    errors.append({
                        "transaction": tx,
                        "error": result["error"]
                    })
            except Exception as e:
                errors.append({
                    "transaction": tx,
                    "error": str(e)
                })
                
        return {
            "processed": success_count,
            "failed": len(errors),
            "errors": errors
        }
