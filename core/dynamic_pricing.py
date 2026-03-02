from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging
import math

logger = logging.getLogger(__name__)

class DynamicPricing:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    async def calculate_optimal_price(self, product_id: str) -> Dict[str, Any]:
        """Calculate optimal price based on demand, competition, and other factors."""
        try:
            # Get product details
            res = await self.execute_sql(f"""
                SELECT * FROM products WHERE id = '{product_id}'
            """)
            product = res.get("rows", [{}])[0]
            
            if not product:
                return {"success": False, "error": "Product not found"}
                
            # Get pricing history
            history_res = await self.execute_sql(f"""
                SELECT price, sales_volume, timestamp 
                FROM pricing_history 
                WHERE product_id = '{product_id}'
                ORDER BY timestamp DESC
                LIMIT 100
            """)
            history = history_res.get("rows", [])
            
            # Get competitor pricing
            competitor_res = await self.execute_sql(f"""
                SELECT price FROM competitor_prices 
                WHERE product_id = '{product_id}'
                ORDER BY updated_at DESC
                LIMIT 10
            """)
            competitor_prices = [r["price"] for r in competitor_res.get("rows", [])]
            
            # Calculate optimal price using machine learning or heuristic
            optimal_price = self._calculate_price(
                product.get("cost_price"),
                competitor_prices,
                history
            )
            
            return {
                "success": True,
                "optimal_price": optimal_price,
                "current_price": product.get("price"),
                "product_id": product_id
            }
            
        except Exception as e:
            logger.error(f"Price calculation failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def _calculate_price(self, cost_price: float, competitor_prices: list, history: list) -> float:
        """Calculate optimal price using heuristic approach."""
        if not competitor_prices:
            return cost_price * 1.5
            
        # Calculate price based on competitor average
        avg_competitor = sum(competitor_prices) / len(competitor_prices)
        
        # Adjust based on historical performance
        if history:
            best_performing = max(history, key=lambda x: x["sales_volume"])
            price_adjustment = best_performing["price"] / avg_competitor
            avg_competitor *= price_adjustment
            
        # Ensure minimum margin
        min_price = cost_price * 1.2
        return max(min_price, avg_competitor)
