"""
Core strategy execution logic for revenue automation.
Handles strategy lifecycle, payment processing, and error recovery.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.database import query_db
from core.payment_processor import PaymentProcessor

logger = logging.getLogger(__name__)

class StrategyExecutor:
    """Execute revenue strategies with automated monitoring and recovery."""
    
    def __init__(self, payment_processor: PaymentProcessor):
        self.payment_processor = payment_processor
        self.max_retries = 3
        self.retry_delay = 60  # seconds
        
    async def execute_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """Execute a revenue strategy with automated retries and monitoring."""
        try:
            # Get strategy details
            strategy = await self._get_strategy(strategy_id)
            if not strategy:
                return {"success": False, "error": "Strategy not found"}
                
            # Validate strategy
            validation = self._validate_strategy(strategy)
            if not validation["valid"]:
                return {"success": False, "error": validation["error"]}
                
            # Execute payment processing
            payment_result = await self._process_payments(strategy)
            if not payment_result["success"]:
                return payment_result
                
            # Update strategy status
            await self._update_strategy_status(strategy_id, "completed")
            
            return {"success": True, "payment_result": payment_result}
            
        except Exception as e:
            logger.error(f"Strategy execution failed: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
            
    async def _get_strategy(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve strategy details from database."""
        try:
            result = await query_db(
                f"SELECT * FROM revenue_strategies WHERE id = '{strategy_id}'"
            )
            return result.get("rows", [{}])[0] if result.get("rows") else None
        except Exception as e:
            logger.error(f"Failed to get strategy: {str(e)}")
            return None
            
    def _validate_strategy(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Validate strategy configuration."""
        required_fields = ["payment_method", "amount", "currency", "schedule"]
        missing = [field for field in required_fields if not strategy.get(field)]
        
        if missing:
            return {"valid": False, "error": f"Missing required fields: {', '.join(missing)}"}
            
        if not isinstance(strategy["amount"], (int, float)) or strategy["amount"] <= 0:
            return {"valid": False, "error": "Invalid amount"}
            
        return {"valid": True}
        
    async def _process_payments(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Process payments with retry logic."""
        retries = 0
        last_error = None
        
        while retries < self.max_retries:
            try:
                payment_result = await self.payment_processor.process_payment(
                    amount=strategy["amount"],
                    currency=strategy["currency"],
                    payment_method=strategy["payment_method"],
                    metadata={
                        "strategy_id": strategy["id"],
                        "description": strategy.get("description", "")
                    }
                )
                
                if payment_result["success"]:
                    return payment_result
                    
                last_error = payment_result.get("error", "Unknown payment error")
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"Payment processing attempt {retries + 1} failed: {last_error}")
                
            retries += 1
            await asyncio.sleep(self.retry_delay)
            
        return {"success": False, "error": f"Payment failed after {self.max_retries} attempts: {last_error}"}
        
    async def _update_strategy_status(self, strategy_id: str, status: str) -> None:
        """Update strategy status in database."""
        try:
            await query_db(
                f"""
                UPDATE revenue_strategies
                SET status = '{status}',
                    updated_at = NOW()
                WHERE id = '{strategy_id}'
                """
            )
        except Exception as e:
            logger.error(f"Failed to update strategy status: {str(e)}")
