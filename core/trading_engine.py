from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Callable
import logging
import math

class TradingEngine:
    """Autonomous trading engine with safety limits and reinvestment logic."""
    
    def __init__(
        self,
        execute_sql: Callable[[str], Dict[str, Any]],
        log_action: Callable[..., Any],
        working_capital: float = 10000.0,
        max_loss_pct: float = 10.0,
        reinvestment_pct: float = 50.0
    ):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.working_capital = working_capital
        self.max_loss_pct = max_loss_pct
        self.reinvestment_pct = reinvestment_pct
        self.max_loss_amount = working_capital * (max_loss_pct / 100.0)
        self.current_loss = 0.0
        self.logger = logging.getLogger(__name__)
        
    def _log_transaction(self, transaction_type: str, amount: float, metadata: Dict[str, Any]) -> bool:
        """Log transaction to database."""
        try:
            metadata_json = json.dumps(metadata).replace("'", "''")
            self.execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source,
                    metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{transaction_type}',
                    {int(amount * 100)},
                    'USD',
                    'trading_engine',
                    '{metadata_json}'::jsonb,
                    NOW(),
                    NOW()
                )
                """
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to log transaction: {str(e)}")
            return False
            
    def execute_trade(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a trade with safety checks."""
        try:
            amount = float(trade_data.get("amount", 0))
            if amount <= 0:
                return {"success": False, "error": "Invalid trade amount"}
                
            # Check loss limits
            if self.current_loss >= self.max_loss_amount:
                return {"success": False, "error": "Max loss limit reached"}
                
            # Execute trade (mock implementation)
            # TODO: Replace with actual trading logic
            trade_result = self._mock_trade_execution(trade_data)
            
            # Update capital and losses
            if trade_result["profit"] < 0:
                self.current_loss += abs(trade_result["profit"])
            self.working_capital += trade_result["profit"]
            
            # Log transaction
            self._log_transaction(
                "revenue" if trade_result["profit"] > 0 else "cost",
                abs(trade_result["profit"]),
                {
                    "trade_data": trade_data,
                    "result": trade_result,
                    "working_capital": self.working_capital,
                    "current_loss": self.current_loss
                }
            )
            
            # Reinvest profits
            if trade_result["profit"] > 0:
                reinvest_amount = trade_result["profit"] * (self.reinvestment_pct / 100.0)
                self.working_capital += reinvest_amount
                self._log_transaction(
                    "reinvestment",
                    reinvest_amount,
                    {"source": "profit_reinvestment"}
                )
            
            return {"success": True, "result": trade_result}
            
        except Exception as e:
            self.logger.error(f"Trade execution failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def _mock_trade_execution(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock trade execution for testing."""
        # Simulate a trade with random profit/loss
        import random
        profit = random.uniform(-100, 200)
        return {
            "profit": profit,
            "details": {
                "mock_data": True,
                "trade_data": trade_data
            }
        }
        
    def monitor_engine(self) -> Dict[str, Any]:
        """Monitor engine health and performance."""
        try:
            # Get recent transactions
            res = self.execute_sql(
                """
                SELECT 
                    SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as total_revenue_cents,
                    SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as total_cost_cents,
                    COUNT(*) as transaction_count
                FROM revenue_events
                WHERE source = 'trading_engine'
                  AND recorded_at >= NOW() - INTERVAL '1 hour'
                """
            )
            stats = res.get("rows", [{}])[0]
            
            return {
                "success": True,
                "stats": {
                    "working_capital": self.working_capital,
                    "current_loss": self.current_loss,
                    "max_loss_pct": self.max_loss_pct,
                    "recent_revenue": (stats.get("total_revenue_cents") or 0) / 100.0,
                    "recent_costs": (stats.get("total_cost_cents") or 0) / 100.0,
                    "recent_transactions": stats.get("transaction_count") or 0
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
