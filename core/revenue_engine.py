import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

class RevenueEngine:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.circuit_breaker = False
        self.last_error = None
        self.error_count = 0
        
    async def process_payment_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle payment webhook events."""
        try:
            if self.circuit_breaker:
                return {"success": False, "error": "Circuit breaker active"}
                
            event_type = payload.get("type")
            amount_cents = int(payload.get("amount", 0))
            currency = payload.get("currency", "USD")
            source = payload.get("source", "unknown")
            metadata = payload.get("metadata", {})
            
            if event_type not in ["payment.succeeded", "payment.failed"]:
                return {"success": False, "error": "Invalid event type"}
                
            sql = f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                '{event_type}',
                {amount_cents},
                '{currency}',
                '{source}',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
            """
            
            await self.execute_sql(sql)
            self.error_count = 0
            return {"success": True}
            
        except Exception as e:
            self.error_count += 1
            if self.error_count > 5:
                self.circuit_breaker = True
            self.last_error = str(e)
            logger.error(f"Payment webhook processing failed: {e}")
            return {"success": False, "error": str(e)}
            
    async def autonomous_loop(self) -> None:
        """Run continuous revenue monitoring and processing."""
        while True:
            try:
                if self.circuit_breaker:
                    logger.warning("Circuit breaker active - skipping cycle")
                    time.sleep(60)
                    continue
                    
                # Check for pending transactions
                res = await self.execute_sql("""
                    SELECT COUNT(*) as pending 
                    FROM revenue_events 
                    WHERE status = 'pending'
                """)
                pending = res.get("rows", [{}])[0].get("pending", 0)
                
                if pending > 0:
                    await self.process_pending_transactions()
                    
                # Check circuit breaker status
                if self.error_count > 0 and time.time() - self.last_error > 300:
                    self.circuit_breaker = False
                    self.error_count = 0
                    
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Autonomous loop error: {e}")
                time.sleep(60)
                
    async def process_pending_transactions(self) -> None:
        """Process pending revenue events."""
        try:
            res = await self.execute_sql("""
                SELECT id, event_type, amount_cents, currency, source, metadata
                FROM revenue_events
                WHERE status = 'pending'
                LIMIT 10
            """)
            
            for row in res.get("rows", []):
                await self._process_transaction(row)
                
        except Exception as e:
            logger.error(f"Transaction processing failed: {e}")
            self.error_count += 1
            
    async def _process_transaction(self, transaction: Dict[str, Any]) -> None:
        """Process individual transaction."""
        try:
            transaction_id = transaction.get("id")
            await self.execute_sql(f"""
                UPDATE revenue_events
                SET status = 'processed',
                    processed_at = NOW()
                WHERE id = '{transaction_id}'
            """)
            
        except Exception as e:
            logger.error(f"Failed to process transaction {transaction_id}: {e}")
            raise
