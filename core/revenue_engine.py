"""
Core Revenue Engine - Handles transaction processing, revenue calculations,
and automated decision making for revenue generation strategies.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class RevenueEngine:
    """Core engine for revenue generation and transaction processing."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    def process_transaction(self, transaction_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Process a revenue transaction with validation and logging.
        
        Args:
            transaction_data: Dictionary containing transaction details
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Validate required fields
            required_fields = ['event_type', 'amount_cents', 'currency', 'source']
            for field in required_fields:
                if not transaction_data.get(field):
                    return False, f"Missing required field: {field}"
                    
            # Validate amount
            try:
                amount = int(transaction_data['amount_cents'])
                if amount <= 0:
                    return False, "Amount must be positive"
            except ValueError:
                return False, "Invalid amount format"
                
            # Prepare metadata
            metadata = transaction_data.get('metadata', {})
            if isinstance(metadata, dict):
                metadata_json = json.dumps(metadata)
            else:
                metadata_json = "{}"
                
            # Insert transaction
            sql = f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                '{transaction_data['event_type']}',
                {amount},
                '{transaction_data['currency']}',
                '{transaction_data['source']}',
                '{metadata_json}'::jsonb,
                NOW(),
                NOW()
            )
            """
            self.execute_sql(sql)
            
            self.log_action(
                "revenue.transaction_processed",
                f"Processed {transaction_data['event_type']} transaction",
                level="info",
                output_data={
                    "amount_cents": amount,
                    "source": transaction_data['source']
                }
            )
            
            return True, None
            
        except Exception as e:
            logger.error(f"Transaction processing failed: {str(e)}")
            self.log_action(
                "revenue.transaction_failed",
                f"Failed to process transaction: {str(e)}",
                level="error",
                error_data={"error": str(e)}
            )
            return False, str(e)
            
    def calculate_revenue_metrics(self, period_days: int = 30) -> Dict[str, Any]:
        """
        Calculate key revenue metrics for the given period.
        
        Args:
            period_days: Number of days to calculate metrics for
            
        Returns:
            Dictionary containing revenue metrics
        """
        try:
            # Get daily revenue breakdown
            sql = f"""
            SELECT 
                DATE(recorded_at) as date,
                SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents,
                SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as cost_cents,
                COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count
            FROM revenue_events
            WHERE recorded_at >= NOW() - INTERVAL '{period_days} days'
            GROUP BY DATE(recorded_at)
            ORDER BY date DESC
            """
            result = self.execute_sql(sql)
            daily_data = result.get("rows", [])
            
            # Calculate totals
            total_revenue = sum(d['revenue_cents'] for d in daily_data)
            total_cost = sum(d['cost_cents'] for d in daily_data)
            total_transactions = sum(d['transaction_count'] for d in daily_data)
            
            return {
                "daily": daily_data,
                "total_revenue_cents": total_revenue,
                "total_cost_cents": total_cost,
                "total_transactions": total_transactions,
                "net_profit_cents": total_revenue - total_cost,
                "period_days": period_days
            }
            
        except Exception as e:
            logger.error(f"Revenue metrics calculation failed: {str(e)}")
            self.log_action(
                "revenue.metrics_failed",
                f"Failed to calculate revenue metrics: {str(e)}",
                level="error",
                error_data={"error": str(e)}
            )
            return {}
            
    def optimize_revenue_strategy(self, strategy_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize revenue generation strategy based on historical data.
        
        Args:
            strategy_params: Parameters for the optimization strategy
            
        Returns:
            Dictionary containing optimization results
        """
        try:
            # Get historical performance data
            sql = """
            SELECT 
                source,
                SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents,
                SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as cost_cents,
                COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count
            FROM revenue_events
            WHERE recorded_at >= NOW() - INTERVAL '90 days'
            GROUP BY source
            ORDER BY revenue_cents DESC
            """
            result = self.execute_sql(sql)
            source_data = result.get("rows", [])
            
            # Analyze performance
            optimized_strategy = {
                "top_performing_sources": [],
                "recommended_budget_allocation": {},
                "roi_by_source": {}
            }
            
            for source in source_data:
                revenue = source['revenue_cents']
                cost = source['cost_cents']
                roi = ((revenue - cost) / cost * 100) if cost > 0 else 0
                
                optimized_strategy['top_performing_sources'].append(source['source'])
                optimized_strategy['roi_by_source'][source['source']] = roi
                
            # Calculate budget allocation
            total_revenue = sum(s['revenue_cents'] for s in source_data)
            if total_revenue > 0:
                for source in source_data:
                    allocation = (source['revenue_cents'] / total_revenue) * 100
                    optimized_strategy['recommended_budget_allocation'][source['source']] = round(allocation, 2)
                    
            self.log_action(
                "revenue.strategy_optimized",
                "Optimized revenue generation strategy",
                level="info",
                output_data=optimized_strategy
            )
            
            return optimized_strategy
            
        except Exception as e:
            logger.error(f"Strategy optimization failed: {str(e)}")
            self.log_action(
                "revenue.optimization_failed",
                f"Failed to optimize revenue strategy: {str(e)}",
                level="error",
                error_data={"error": str(e)}
            )
            return {}
