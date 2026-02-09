"""
Autonomous Revenue System - Automated trading and data marketplace revenue streams.
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import random
import json
import logging
from dataclasses import dataclass

from core.database import query_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Trade:
    symbol: str
    quantity: float
    price: float
    side: str  # 'buy' or 'sell'
    timestamp: datetime

@dataclass
class DataProduct:
    name: str
    price: float
    units_sold: int
    timestamp: datetime

class RevenueSystem:
    def __init__(self, max_daily_loss: float = 1000.0, max_position_size: float = 5000.0):
        self.max_daily_loss = max_daily_loss
        self.max_position_size = max_position_size
        self.daily_pnl = 0.0
        self.positions: Dict[str, float] = {}
        self.circuit_breaker = False
        self.last_trade_time = datetime.now(timezone.utc)
        
    def check_risk_limits(self) -> bool:
        """Check if we've hit any risk limits."""
        if self.circuit_breaker:
            return False
            
        if self.daily_pnl < -self.max_daily_loss:
            logger.warning(f"Daily loss limit hit: {self.daily_pnl}")
            self.trigger_circuit_breaker()
            return False
            
        return True
        
    def trigger_circuit_breaker(self) -> None:
        """Halt all trading activity."""
        self.circuit_breaker = True
        logger.error("Circuit breaker triggered - all trading suspended")
        
    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker after manual review."""
        self.circuit_breaker = False
        self.daily_pnl = 0.0
        logger.info("Circuit breaker reset")
        
    async def execute_trade(self, symbol: str, quantity: float, price: float, side: str) -> Optional[Trade]:
        """Execute a trade with risk checks."""
        if not self.check_risk_limits():
            return None
            
        # Simulate trade execution
        trade = Trade(
            symbol=symbol,
            quantity=quantity,
            price=price,
            side=side,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Update position
        if symbol not in self.positions:
            self.positions[symbol] = 0.0
            
        position_change = quantity if side == 'buy' else -quantity
        self.positions[symbol] += position_change
        
        # Log revenue event
        revenue_cents = int(quantity * price * 100)
        await self.log_revenue_event(
            event_type='trade',
            amount_cents=revenue_cents,
            source='trading',
            metadata={
                'symbol': symbol,
                'quantity': quantity,
                'price': price,
                'side': side
            }
        )
        
        self.last_trade_time = trade.timestamp
        return trade
        
    async def sell_data_product(self, product_name: str, price: float, units: int = 1) -> Optional[DataProduct]:
        """Sell units of a data product."""
        if not self.check_risk_limits():
            return None
            
        product = DataProduct(
            name=product_name,
            price=price,
            units_sold=units,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Log revenue event
        revenue_cents = int(price * units * 100)
        await self.log_revenue_event(
            event_type='data_sale',
            amount_cents=revenue_cents,
            source='data_marketplace',
            metadata={
                'product': product_name,
                'units': units,
                'price': price
            }
        )
        
        return product
        
    async def log_revenue_event(self, event_type: str, amount_cents: int, source: str, metadata: Dict) -> None:
        """Log revenue event to database."""
        try:
            metadata_json = json.dumps(metadata).replace("'", "''")
            await query_db(f"""
                INSERT INTO revenue_events (
                    id,
                    event_type,
                    amount_cents,
                    currency,
                    source,
                    metadata,
                    recorded_at,
                    created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{event_type}',
                    {amount_cents},
                    'USD',
                    '{source}',
                    '{metadata_json}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
        except Exception as e:
            logger.error(f"Failed to log revenue event: {str(e)}")
            
    async def reconcile_positions(self) -> None:
        """Reconcile system positions with actual holdings."""
        try:
            # Get current positions from database
            result = await query_db("""
                SELECT symbol, SUM(quantity) as position
                FROM trades
                GROUP BY symbol
            """)
            
            db_positions = {r['symbol']: r['position'] for r in result.get('rows', [])}
            
            # Compare with system positions
            discrepancies = []
            for symbol, position in self.positions.items():
                db_position = db_positions.get(symbol, 0.0)
                if abs(position - db_position) > 0.0001:  # Account for floating point
                    discrepancies.append({
                        'symbol': symbol,
                        'system': position,
                        'database': db_position,
                        'difference': position - db_position
                    })
                    
            if discrepancies:
                logger.warning(f"Position discrepancies found: {discrepancies}")
                self.trigger_circuit_breaker()
                
        except Exception as e:
            logger.error(f"Reconciliation failed: {str(e)}")
            self.trigger_circuit_breaker()
