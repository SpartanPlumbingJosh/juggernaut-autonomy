"""
Autonomous Revenue Engine - Core monetization logic for AI-driven revenue generation.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable

class AutonomousRevenueEngine:
    """Core engine for autonomous revenue generation."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.min_profit_margin = 0.20  # Minimum acceptable profit margin
        self.max_risk_exposure = 1000.00  # Max risk per transaction
        self.daily_revenue_target = 5000.00  # Daily revenue target
        
    async def execute_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a revenue transaction with risk management."""
        try:
            # Validate transaction
            if not self._validate_transaction(transaction):
                return {"success": False, "error": "Invalid transaction"}
                
            # Calculate expected profit
            profit = self._calculate_expected_profit(transaction)
            if profit < self.min_profit_margin * float(transaction.get("amount", 0)):
                return {"success": False, "error": "Insufficient profit margin"}
                
            # Check risk exposure
            if float(transaction.get("amount", 0)) > self.max_risk_exposure:
                return {"success": False, "error": "Exceeds risk exposure limit"}
                
            # Record transaction
            transaction_id = await self._record_transaction(transaction)
            if not transaction_id:
                return {"success": False, "error": "Failed to record transaction"}
                
            # Update monitoring metrics
            await self._update_monitoring_metrics(transaction)
            
            return {"success": True, "transaction_id": transaction_id}
            
        except Exception as e:
            await self.log_action(
                "revenue.transaction_failed",
                f"Transaction failed: {str(e)}",
                level="error",
                error_data={"transaction": transaction, "error": str(e)}
            )
            return {"success": False, "error": str(e)}
            
    def _validate_transaction(self, transaction: Dict[str, Any]) -> bool:
        """Validate transaction structure and values."""
        required_fields = ["amount", "currency", "source", "type"]
        return all(field in transaction for field in required_fields)
        
    def _calculate_expected_profit(self, transaction: Dict[str, Any]) -> float:
        """Calculate expected profit based on transaction details."""
        amount = float(transaction.get("amount", 0))
        cost = float(transaction.get("cost", 0))
        return amount - cost
        
    async def _record_transaction(self, transaction: Dict[str, Any]) -> Optional[str]:
        """Record transaction in database."""
        try:
            result = await self.execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{transaction.get("type")}',
                    {int(float(transaction.get("amount", 0)) * 100)},
                    '{transaction.get("currency", "USD")}',
                    '{transaction.get("source")}',
                    '{json.dumps(transaction.get("metadata", {}))}',
                    NOW(),
                    NOW()
                )
                RETURNING id
                """
            )
            return result.get("rows", [{}])[0].get("id")
        except Exception as e:
            await self.log_action(
                "revenue.recording_failed",
                f"Failed to record transaction: {str(e)}",
                level="error",
                error_data={"transaction": transaction, "error": str(e)}
            )
            return None
            
    async def _update_monitoring_metrics(self, transaction: Dict[str, Any]) -> None:
        """Update monitoring metrics for the revenue engine."""
        try:
            # Update daily totals
            await self.execute_sql(
                f"""
                INSERT INTO revenue_monitoring (date, total_revenue, transaction_count)
                VALUES (CURRENT_DATE, {float(transaction.get("amount", 0))}, 1)
                ON CONFLICT (date) DO UPDATE SET
                    total_revenue = revenue_monitoring.total_revenue + EXCLUDED.total_revenue,
                    transaction_count = revenue_monitoring.transaction_count + EXCLUDED.transaction_count
                """
            )
            
            # Update source performance
            await self.execute_sql(
                f"""
                INSERT INTO revenue_source_performance (source, total_revenue, transaction_count)
                VALUES ('{transaction.get("source")}', {float(transaction.get("amount", 0))}, 1)
                ON CONFLICT (source) DO UPDATE SET
                    total_revenue = revenue_source_performance.total_revenue + EXCLUDED.total_revenue,
                    transaction_count = revenue_source_performance.transaction_count + EXCLUDED.transaction_count
                """
            )
        except Exception as e:
            await self.log_action(
                "revenue.monitoring_update_failed",
                f"Failed to update monitoring metrics: {str(e)}",
                level="error",
                error_data={"transaction": transaction, "error": str(e)}
            )
            
    async def check_engine_health(self) -> Dict[str, Any]:
        """Check engine health and performance metrics."""
        try:
            # Get daily performance
            daily_result = await self.execute_sql(
                """
                SELECT total_revenue, transaction_count
                FROM revenue_monitoring
                WHERE date = CURRENT_DATE
                LIMIT 1
                """
            )
            daily = daily_result.get("rows", [{}])[0]
            
            # Get source performance
            source_result = await self.execute_sql(
                """
                SELECT source, total_revenue, transaction_count
                FROM revenue_source_performance
                ORDER BY total_revenue DESC
                LIMIT 5
                """
            )
            sources = source_result.get("rows", [])
            
            return {
                "success": True,
                "daily_revenue": daily.get("total_revenue", 0),
                "daily_transactions": daily.get("transaction_count", 0),
                "top_sources": sources,
                "status": "healthy" if daily.get("total_revenue", 0) >= self.daily_revenue_target else "needs_attention"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
