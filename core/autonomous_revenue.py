"""
Autonomous Revenue Generation System

Implements automated revenue generation based on validated research findings
with safety limits, payment processing integration, and comprehensive logging.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from core.database import query_db, execute_db
from core.payment_processor import PaymentProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutonomousRevenueGenerator:
    """Core class for managing autonomous revenue generation."""
    
    def __init__(self):
        self.payment_processor = PaymentProcessor()
        self.daily_limit_usd = 100.0  # Max daily spend
        self.max_transaction_usd = 10.0  # Max per transaction
        self.min_roi_threshold = 1.2  # Minimum ROI to proceed
        self.cooldown_hours = 6  # Hours between attempts
        
    async def get_active_revenue_streams(self) -> List[Dict[str, Any]]:
        """Get validated revenue streams from database."""
        try:
            result = await query_db("""
                SELECT id, name, roi, cost_per_conversion, conversion_rate, 
                       daily_limit, status, last_run_at
                FROM revenue_streams
                WHERE status = 'active'
                AND roi >= %s
                ORDER BY roi DESC
            """, [self.min_roi_threshold])
            return result.get("rows", [])
        except Exception as e:
            logger.error(f"Failed to get revenue streams: {e}")
            return []
            
    async def check_daily_limit(self) -> Tuple[bool, float]:
        """Check if we've hit the daily spending limit."""
        try:
            today = datetime.utcnow().date()
            result = await query_db("""
                SELECT COALESCE(SUM(amount_usd), 0) as total_spent
                FROM revenue_transactions
                WHERE created_at >= %s
            """, [today])
            total_spent = float(result.get("rows", [{}])[0].get("total_spent", 0))
            return (total_spent >= self.daily_limit_usd, total_spent)
        except Exception as e:
            logger.error(f"Failed to check daily limit: {e}")
            return (True, self.daily_limit_usd)
            
    async def execute_revenue_stream(self, stream: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single revenue stream transaction."""
        try:
            # Check cooldown period
            last_run = stream.get("last_run_at")
            if last_run and (datetime.utcnow() - last_run) < timedelta(hours=self.cooldown_hours):
                return {"success": False, "error": "Cooldown period active"}
                
            # Calculate transaction amount
            amount_usd = min(
                float(stream.get("daily_limit", 0)),
                self.max_transaction_usd,
                self.daily_limit_usd - await self.check_daily_limit()[1]
            )
            
            if amount_usd <= 0:
                return {"success": False, "error": "Insufficient funds"}
                
            # Process payment
            payment_result = await self.payment_processor.process_payment(
                amount_usd,
                stream.get("name"),
                metadata={"stream_id": stream.get("id")}
            )
            
            if not payment_result.get("success"):
                return payment_result
                
            # Record transaction
            await execute_db("""
                INSERT INTO revenue_transactions (
                    stream_id, amount_usd, status, 
                    payment_id, created_at
                ) VALUES (%s, %s, %s, %s, NOW())
            """, [
                stream.get("id"),
                amount_usd,
                "completed",
                payment_result.get("payment_id")
            ])
            
            # Update stream last run
            await execute_db("""
                UPDATE revenue_streams
                SET last_run_at = NOW()
                WHERE id = %s
            """, [stream.get("id")])
            
            return {
                "success": True,
                "amount_usd": amount_usd,
                "stream_id": stream.get("id")
            }
            
        except Exception as e:
            logger.error(f"Failed to execute revenue stream: {e}")
            return {"success": False, "error": str(e)}
            
    async def run_cycle(self) -> Dict[str, Any]:
        """Run a full cycle of autonomous revenue generation."""
        try:
            # Check if we can proceed
            limit_reached, total_spent = await self.check_daily_limit()
            if limit_reached:
                return {"success": False, "error": "Daily limit reached"}
                
            # Get active streams
            streams = await self.get_active_revenue_streams()
            if not streams:
                return {"success": False, "error": "No active streams"}
                
            # Execute top stream
            result = await self.execute_revenue_stream(streams[0])
            
            if not result.get("success"):
                return result
                
            # Log success
            logger.info(f"Successfully executed revenue stream: {result}")
            return {
                "success": True,
                "amount_usd": result.get("amount_usd"),
                "stream_id": result.get("stream_id"),
                "total_spent": total_spent + result.get("amount_usd")
            }
            
        except Exception as e:
            logger.error(f"Failed to run revenue cycle: {e}")
            return {"success": False, "error": str(e)}
