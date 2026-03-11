"""
Autonomous Revenue System - Core execution engine for revenue-generating systems.

Supported systems:
- Arbitrage bots
- Content pipelines 
- Service APIs

Features:
- Automated execution with scheduling
- Integrated payment processing
- Transaction recording
- Circuit breakers for risk management
- Comprehensive logging
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable

class RevenueSystem:
    """Core class for managing autonomous revenue systems."""
    
    def __init__(
        self,
        execute_sql: Callable[[str], Dict[str, Any]],
        log_action: Callable[..., Any],
        system_type: str,
        config: Dict[str, Any]
    ):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.system_type = system_type
        self.config = config
        self.circuit_breaker = False
        self.last_run = None
        self.total_profit = 0.0
        self.total_revenue = 0.0
        self.total_cost = 0.0
        
    def _record_transaction(
        self,
        amount: float,
        currency: str,
        source: str,
        metadata: Dict[str, Any],
        event_type: str = "revenue"
    ) -> bool:
        """Record a financial transaction to the database."""
        try:
            metadata_json = json.dumps(metadata).replace("'", "''")
            self.execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, 
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{event_type}',
                    {int(amount * 100)},
                    '{currency}',
                    '{source}',
                    '{metadata_json}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            return True
        except Exception as e:
            self.log_action(
                "revenue.transaction_failed",
                f"Failed to record transaction: {str(e)}",
                level="error",
                error_data={
                    "amount": amount,
                    "currency": currency,
                    "source": source,
                    "error": str(e)
                }
            )
            return False
            
    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker conditions are met."""
        try:
            # Check daily loss limit
            res = self.execute_sql(f"""
                SELECT SUM(
                    CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END
                ) - SUM(
                    CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END
                ) as net_profit_cents
                FROM revenue_events
                WHERE recorded_at >= NOW() - INTERVAL '1 day'
                  AND source = '{self.system_type}'
            """)
            net_profit = (res.get("rows", [{}])[0].get("net_profit_cents") or 0) / 100
            
            if net_profit < -abs(self.config.get("daily_loss_limit", 100)):
                self.circuit_breaker = True
                self.log_action(
                    "revenue.circuit_breaker_triggered",
                    f"Circuit breaker triggered: Daily loss limit exceeded ({net_profit})",
                    level="warning",
                    output_data={"net_profit": net_profit}
                )
                return True
                
            return False
        except Exception as e:
            self.log_action(
                "revenue.circuit_breaker_failed",
                f"Failed to check circuit breaker: {str(e)}",
                level="error",
                error_data={"error": str(e)}
            )
            return False
            
    def execute(self) -> Dict[str, Any]:
        """Execute one cycle of the revenue system."""
        if self.circuit_breaker:
            return {"success": False, "error": "Circuit breaker active"}
            
        if self._check_circuit_breaker():
            return {"success": False, "error": "Circuit breaker conditions met"}
            
        try:
            # Execute system-specific logic
            result = self._execute_system()
            
            # Record transactions
            for tx in result.get("transactions", []):
                self._record_transaction(
                    amount=tx["amount"],
                    currency=tx["currency"],
                    source=self.system_type,
                    metadata=tx.get("metadata", {})
                )
                
            # Update totals
            self.total_profit += result.get("net_profit", 0)
            self.total_revenue += result.get("total_revenue", 0)
            self.total_cost += result.get("total_cost", 0)
            
            self.last_run = datetime.now(timezone.utc)
            return {"success": True, **result}
            
        except Exception as e:
            self.log_action(
                "revenue.execution_failed",
                f"Revenue system execution failed: {str(e)}",
                level="error",
                error_data={"error": str(e)}
            )
            return {"success": False, "error": str(e)}
            
    def _execute_system(self) -> Dict[str, Any]:
        """System-specific execution logic to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _execute_system")
        
    def get_status(self) -> Dict[str, Any]:
        """Get current system status."""
        return {
            "system_type": self.system_type,
            "circuit_breaker": self.circuit_breaker,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "total_profit": self.total_profit,
            "total_revenue": self.total_revenue,
            "total_cost": self.total_cost,
            "config": self.config
        }
