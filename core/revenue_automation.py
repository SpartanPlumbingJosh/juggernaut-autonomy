"""
Core Revenue Automation System - Handles payment processing, scaling, and monitoring.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("revenue_automation.log"),
        logging.StreamHandler()
    ]
)

class RevenueAutomation:
    """Core class for handling revenue generation automation."""
    
    def __init__(self):
        self.min_workers = 1
        self.max_workers = 10
        self.current_workers = 1
        self.last_scale_check = datetime.now(timezone.utc)
        
    async def process_payment_webhook(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle payment webhook events."""
        try:
            event_type = event.get("type")
            amount_cents = int(event.get("amount_cents", 0))
            currency = event.get("currency", "USD")
            source = event.get("source", "unknown")
            metadata = event.get("metadata", {})
            
            # Validate required fields
            if not event_type or amount_cents <= 0:
                return {"success": False, "error": "Invalid event data"}
            
            # Record transaction
            transaction_id = await self._record_transaction(
                event_type=event_type,
                amount_cents=amount_cents,
                currency=currency,
                source=source,
                metadata=metadata
            )
            
            # Scale workers based on load
            await self._scale_workers()
            
            return {"success": True, "transaction_id": transaction_id}
            
        except Exception as e:
            logging.error(f"Payment processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _record_transaction(
        self,
        event_type: str,
        amount_cents: int,
        currency: str,
        source: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Record a revenue transaction in the database."""
        try:
            result = await query_db(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source, metadata, recorded_at
                ) VALUES (
                    gen_random_uuid(),
                    '{event_type}',
                    {amount_cents},
                    '{currency}',
                    '{source}',
                    '{json.dumps(metadata)}'::jsonb,
                    NOW()
                )
                RETURNING id
                """
            )
            return result.get("rows", [{}])[0].get("id", "")
        except Exception as e:
            logging.error(f"Failed to record transaction: {str(e)}")
            raise
    
    async def _scale_workers(self) -> None:
        """Scale worker instances based on current load."""
        now = datetime.now(timezone.utc)
        if (now - self.last_scale_check).total_seconds() < 60:
            return
            
        try:
            # Get transaction rate
            result = await query_db(
                """
                SELECT COUNT(*) as count
                FROM revenue_events
                WHERE recorded_at >= NOW() - INTERVAL '1 minute'
                """
            )
            transaction_rate = result.get("rows", [{}])[0].get("count", 0)
            
            # Calculate desired workers
            desired_workers = min(
                max(
                    transaction_rate // 10,  # 10 transactions per worker
                    self.min_workers
                ),
                self.max_workers
            )
            
            if desired_workers != self.current_workers:
                # TODO: Implement actual scaling logic
                self.current_workers = desired_workers
                logging.info(f"Scaling workers to {self.current_workers}")
                
            self.last_scale_check = now
            
        except Exception as e:
            logging.error(f"Scaling check failed: {str(e)}")
    
    async def monitor_system(self) -> None:
        """Continuous system monitoring."""
        while True:
            try:
                # Check system health
                await self._check_health()
                
                # Scale if needed
                await self._scale_workers()
                
                # Sleep for monitoring interval
                await asyncio.sleep(60)
                
            except Exception as e:
                logging.error(f"Monitoring failed: {str(e)}")
                await asyncio.sleep(10)
    
    async def _check_health(self) -> None:
        """Perform system health checks."""
        try:
            # Check database connectivity
            await query_db("SELECT 1")
            
            # Check transaction processing
            result = await query_db(
                """
                SELECT COUNT(*) as count
                FROM revenue_events
                WHERE recorded_at >= NOW() - INTERVAL '1 minute'
                """
            )
            transaction_count = result.get("rows", [{}])[0].get("count", 0)
            
            logging.info(f"System health check: {transaction_count} transactions/min")
            
        except Exception as e:
            logging.error(f"Health check failed: {str(e)}")
            raise
