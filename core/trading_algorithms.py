"""
Algorithmic trading strategies for revenue optimization.
Implements mean reversion, momentum, and arbitrage strategies.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any

class TradingAlgorithms:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql

    async def mean_reversion_strategy(self, symbol: str, lookback: int = 20, threshold: float = 1.5) -> Dict[str, Any]:
        """Mean reversion trading strategy."""
        sql = f"""
        SELECT 
            timestamp,
            price
        FROM market_data
        WHERE symbol = '{symbol}'
        ORDER BY timestamp DESC
        LIMIT {lookback}
        """
        
        result = await self.execute_sql(sql)
        prices = [row['price'] for row in result.get("rows", [])]
        
        if len(prices) < lookback:
            return {"success": False, "error": "Not enough data points"}
        
        # Calculate z-score
        prices = np.array(prices)
        mean = np.mean(prices)
        std = np.std(prices)
        z_score = (prices[-1] - mean) / std
        
        # Trading signal
        if z_score > threshold:
            signal = "sell"
        elif z_score < -threshold:
            signal = "buy"
        else:
            signal = "hold"
            
        return {
            "success": True,
            "symbol": symbol,
            "current_price": prices[-1],
            "mean": mean,
            "std": std,
            "z_score": z_score,
            "signal": signal
        }

    async def momentum_strategy(self, symbol: str, short_window: int = 10, long_window: int = 50) -> Dict[str, Any]:
        """Momentum trading strategy."""
        sql = f"""
        SELECT 
            timestamp,
            price
        FROM market_data
        WHERE symbol = '{symbol}'
        ORDER BY timestamp DESC
        LIMIT {long_window}
        """
        
        result = await self.execute_sql(sql)
        prices = [row['price'] for row in result.get("rows", [])]
        
        if len(prices) < long_window:
            return {"success": False, "error": "Not enough data points"}
        
        # Calculate moving averages
        short_ma = np.mean(prices[-short_window:])
        long_ma = np.mean(prices)
        
        # Trading signal
        if short_ma > long_ma:
            signal = "buy"
        else:
            signal = "sell"
            
        return {
            "success": True,
            "symbol": symbol,
            "current_price": prices[-1],
            "short_ma": short_ma,
            "long_ma": long_ma,
            "signal": signal
        }

    async def arbitrage_opportunities(self, pairs: List[Dict[str, str]], threshold: float = 0.01) -> Dict[str, Any]:
        """Find arbitrage opportunities between trading pairs."""
        opportunities = []
        
        for pair in pairs:
            sql = f"""
            SELECT 
                symbol,
                price
            FROM market_data
            WHERE symbol IN ('{pair['asset1']}', '{pair['asset2']}')
            ORDER BY timestamp DESC
            LIMIT 1
            """
            
            result = await self.execute_sql(sql)
            prices = {row['symbol']: row['price'] for row in result.get("rows", [])}
            
            if len(prices) == 2:
                spread = abs(prices[pair['asset1']] - prices[pair['asset2']])
                if spread > threshold:
                    opportunities.append({
                        "pair": pair,
                        "spread": spread,
                        "prices": prices
                    })
                    
        return {
            "success": True,
            "opportunities": opportunities,
            "threshold": threshold
        }
