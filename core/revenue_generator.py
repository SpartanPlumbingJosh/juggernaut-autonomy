"""
Core Revenue Generation System - Handles revenue streams, payment processing, and safety mechanisms.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable
import random
import math
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RevenueTransaction:
    """Represents a single revenue transaction"""
    amount_cents: int
    currency: str = "USD"
    source: str = "unknown"
    metadata: Dict[str, Any] = None
    recorded_at: datetime = datetime.now(timezone.utc)
    
    @property
    def amount(self) -> float:
        """Convert cents to dollars"""
        return self.amount_cents / 100

class RevenueGenerator:
    """Core revenue generation system with circuit breakers and safety checks"""
    
    def __init__(self, db_executor: Callable[[str], Dict[str, Any]], max_rate: float = 10.0):
        """
        Args:
            db_executor: Function to execute SQL queries
            max_rate: Maximum transactions per second (rate limiting)
        """
        self.db_executor = db_executor
        self.max_rate = max_rate
        self.last_transaction_time = 0
        self.is_circuit_open = False
        self.error_count = 0
        self.max_error_count = 5
        
    def _check_circuit(self) -> bool:
        """Check if circuit breaker should be opened"""
        if self.error_count >= self.max_error_count:
            self.is_circuit_open = True
            logger.warning("Circuit breaker opened due to excessive errors")
            return False
        return True
    
    def _calculate_delay(self) -> float:
        """Calculate delay needed to stay under rate limit"""
        elapsed = time.time() - self.last_transaction_time
        min_delay = 1.0 / self.max_rate
        return max(0, min_delay - elapsed)
    
    async def process_transaction(self, tx: RevenueTransaction) -> Dict[str, Any]:
        """
        Process a revenue transaction with safety checks and logging
        
        Args:
            tx: RevenueTransaction object
            
        Returns:
            Dict with status and optional error message
        """
        try:
            if self.is_circuit_open:
                return {"status": "failure", "error": "Circuit breaker is open"}
            
            await time.sleep(self._calculate_delay())
            
            # Verify amount is positive
            if tx.amount_cents <= 0:
                return {"status": "failure", "error": "Amount must be positive"}
            
            # Prepare metadata
            tx.metadata = tx.metadata or {}
            tx.metadata.update({"processed_at": datetime.now(timezone.utc).isoformat()})
            
            # Build SQL query
            sql = f"""
            INSERT INTO revenue_events (
                id, 
                event_type, 
                amount_cents, 
                currency, 
                source,
                metadata,
                recorded_at,
                created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {tx.amount_cents},
                '{tx.currency}',
                '{tx.source.replace("'", "''")}',
                '{json.dumps(tx.metadata).replace("'", "''")}',
                '{tx.recorded_at.isoformat()}',
                NOW()
            )
            RETURNING id
            """
            
            # Execute transaction
            result = await self.db_executor(sql)
            
            # Update state
            self.last_transaction_time = time.time()
            self.error_count = max(0, self.error_count - 1)  # Reward success
            
            tx_id = result.get("rows", [{}])[0].get("id")
            return {"status": "success", "transaction_id": tx_id}
            
        except Exception as e:
            self.error_count += 1
            self._check_circuit()
            logger.error(f"Transaction failed: {str(e)}", exc_info=True)
            return {"status": "failure", "error": str(e)}
    
    async def generate_costs(self, tx: RevenueTransaction) -> Dict[str, Any]:
        """
        Record operational costs with same safety checks
        
        Args:
            tx: RevenueTransaction object (for cost)
            
        Returns:
            Dict with status and optional error message
        """
        try:
            if tx.amount_cents >= 0:
                return {"status": "failure", "error": "Cost amounts must be negative"}
                
            # Temporarily mark as cost for processing
            tx.event_type = "cost"
            return await self.process_transaction(tx)
            
        except Exception as e:
            return {"status": "failure", "error": str(e)}
    
    async def reset_circuit(self) -> None:
        """Manually reset circuit breaker"""
        self.is_circuit_open = False 
        self.error_count = 0
        logger.info("Circuit breaker manually reset")
