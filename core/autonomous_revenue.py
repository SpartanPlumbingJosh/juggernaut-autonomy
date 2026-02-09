"""
Autonomous Revenue System - Automated trading and data marketplace with risk controls.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import random
import math

class AutonomousRevenueSystem:
    """Manages automated revenue streams with risk controls."""
    
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.max_daily_loss = 1000.00  # $1000 max daily loss
        self.max_position_size = 5000.00  # $5000 max position
        self.circuit_breaker = False
        self.last_trade_time = None
        self.daily_pnl = 0.0
        
    def check_risk_limits(self) -> bool:
        """Check if we're within risk parameters."""
        if self.circuit_breaker:
            return False
            
        # Check daily PnL
        if self.daily_pnl <= -self.max_daily_loss:
            self.trigger_circuit_breaker("Daily loss limit exceeded")
            return False
            
        return True
        
    def trigger_circuit_breaker(self, reason: str) -> None:
        """Halt trading due to risk violation."""
        self.circuit_breaker = True
        self.log_action(
            "revenue.circuit_breaker",
            f"Circuit breaker triggered: {reason}",
            level="warning"
        )
        
    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker after manual review."""
        self.circuit_breaker = False
        self.log_action(
            "revenue.circuit_breaker",
            "Circuit breaker reset",
            level="info"
        )
        
    def execute_trade(self, symbol: str, amount: float) -> Dict[str, Any]:
        """Execute a simulated trade with risk checks."""
        if not self.check_risk_limits():
            return {"success": False, "error": "Risk limits exceeded"}
            
        if amount > self.max_position_size:
            return {"success": False, "error": "Position size too large"}
            
        # Simulate trade execution
        price = random.uniform(100, 200)  # Simulated price
        fee = abs(amount) * 0.001  # 0.1% fee
        timestamp = datetime.now(timezone.utc)
        
        # Record revenue event
        try:
            self.execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, 
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {int(amount * 100)},
                    'USD',
                    'autonomous_trading',
                    '{json.dumps({
                        "symbol": symbol,
                        "price": price,
                        "fee": fee,
                        "type": "trade"
                    })}'::jsonb,
                    '{timestamp.isoformat()}',
                    NOW()
                )
                """
            )
            
            # Update PnL tracking
            self.daily_pnl += amount - fee
            self.last_trade_time = timestamp
            
            return {"success": True, "price": price, "fee": fee}
            
        except Exception as e:
            self.log_action(
                "revenue.trade_error",
                f"Trade execution failed: {str(e)}",
                level="error"
            )
            return {"success": False, "error": str(e)}
            
    def reconcile_positions(self) -> Dict[str, Any]:
        """Reconcile expected vs actual positions."""
        try:
            # Get expected positions from trades
            res = self.execute_sql(
                """
                SELECT 
                    metadata->>'symbol' as symbol,
                    SUM(amount_cents)/100.0 as net_amount
                FROM revenue_events
                WHERE source = 'autonomous_trading'
                GROUP BY metadata->>'symbol'
                """
            )
            expected = {r['symbol']: r['net_amount'] for r in res.get('rows', [])}
            
            # Simulate getting actual positions (in real system would call exchange API)
            actual = {k: v * random.uniform(0.99, 1.01) for k, v in expected.items()}
            
            # Log any discrepancies
            discrepancies = []
            for symbol in set(expected.keys()).union(actual.keys()):
                diff = actual.get(symbol, 0) - expected.get(symbol, 0)
                if abs(diff) > 0.01:  # $0.01 tolerance
                    discrepancies.append({
                        "symbol": symbol,
                        "expected": expected.get(symbol, 0),
                        "actual": actual.get(symbol, 0),
                        "difference": diff
                    })
                    
            if discrepancies:
                self.log_action(
                    "revenue.reconciliation",
                    f"Found {len(discrepancies)} position discrepancies",
                    level="warning",
                    output_data={"discrepancies": discrepancies}
                )
                
            return {
                "success": True,
                "expected": expected,
                "actual": actual,
                "discrepancies": discrepancies
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def run_strategy(self) -> Dict[str, Any]:
        """Run trading strategy (simplified for example)."""
        if not self.check_risk_limits():
            return {"success": False, "error": "Risk limits exceeded"}
            
        # Simple mean-reversion strategy example
        symbols = ["AAPL", "GOOG", "MSFT", "AMZN"]
        results = []
        
        for symbol in symbols:
            # Random decision to buy/sell
            amount = random.uniform(-100, 100)  # Random amount between -100 and 100
            if abs(amount) > 10:  # Only trade if significant amount
                trade_result = self.execute_trade(symbol, amount)
                results.append({
                    "symbol": symbol,
                    "amount": amount,
                    "result": trade_result
                })
                
        return {
            "success": True,
            "trades": results,
            "daily_pnl": self.daily_pnl,
            "circuit_breaker": self.circuit_breaker
        }
