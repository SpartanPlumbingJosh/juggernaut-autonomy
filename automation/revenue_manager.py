"""
Automated Revenue Manager - Core system for managing revenue capture and executing transactions.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from core.database import query_db
from api.revenue_api import _make_response, _error_response

class RevenueManager:
    def __init__(self, starting_capital: float = 1000.0):
        self.available_capital = starting_capital
        self.is_paused = False
        self.start_time = datetime.now()
        
    async def check_safety_limits(self) -> bool:
        """Check if automated trading should be paused due to losses."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        try:
            sql = f"""
            SELECT 
                SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents,
                SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as cost_cents
            FROM revenue_events
            WHERE recorded_at >= '{today.isoformat()}'
            """

            result = await query_db(sql)
            row = result.get("rows", [{}])[0]
            
            daily_profit_cents = (row.get("revenue_cents", 0) or 0) - (row.get("cost_cents", 0) or 0)
            daily_loss = -daily_profit_cents / 100  # Convert cents to dollars
            
            if daily_loss > 1000:
                self.is_paused = True
                return False
                
            return True
                
        except Exception as e:
            print(f"Error checking safety limits: {e}")
            self.is_paused = True
            return False

    async def execute_transaction(
        self,
        event_type: str,
        amount: float,
        source: str,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Execute a revenue or cost transaction.
        Returns (success, error_message)
        """
        if self.is_paused:
            return (False, "Trading paused due to safety limits")
            
        # Validate amount
        if event_type == "cost" and amount > self.available_capital:
            return (False, "Insufficient capital")
            
        metadata = metadata or {}
        amount_cents = int(amount * 100)  # Store as cents to avoid floating point issues
        
        try:
            sql = f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                '{event_type}',
                {amount_cents},
                'USD',
                '{source.replace("'", "''")}',
                '{json.dumps(metadata).replace("'", "''")}'::jsonb,
                NOW(),
                NOW()
            )
            """

            await query_db(sql)
            
            # Update local capital tracking
            if event_type == "revenue":
                self.available_capital += amount
            else:
                self.available_capital -= amount
                
            return (True, None)
            
        except Exception as e:
            return (False, f"Transaction failed: {str(e)}")

    async def get_current_profit(self, days: int = 1) -> Dict:
        """
        Calculate current profit/loss metrics.
        """
        try:
            sql = f"""
            SELECT 
                SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents,
                SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as cost_cents
            FROM revenue_events
            WHERE recorded_at >= NOW() - INTERVAL '{days} days'
            """

            result = await query_db(sql)
            row = result.get("rows", [{}])[0]
            
            profit_cents = (row.get("revenue_cents", 0) or 0) - (row.get("cost_cents", 0) or 0)
            
            return {
                "revenue": (row.get("revenue_cents", 0) or 0) / 100,
                "cost": (row.get("cost_cents", 0) or 0) / 100,
                "profit": profit_cents / 100,
                "roi": profit_cents / (row.get("cost_cents", 0) or 1) * 100,
                "is_paused": self.is_paused,
                "remaining_capital": self.available_capital
            }
                
        except Exception as e:
            print(f"Error calculating profit: {e}")
            return _error_response(500, "Failed to calculate profit metrics")
