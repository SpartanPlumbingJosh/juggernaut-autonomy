"""
Dynamic pricing optimization engine for revenue growth targets.
Uses demand elasticity models and competitive analysis to maximize revenue.
"""

import numpy as np
from datetime import datetime
from typing import Dict, List, Optional

class PricingOptimizer:
    def __init__(self, 
                 base_price: float,
                 min_price: float,
                 max_price: float,
                 elasticity: float = -1.5,
                 learning_rate: float = 0.01):
        """
        Args:
            base_price: Current price point
            min_price: Minimum viable price 
            max_price: Maximum acceptable price
            elasticity: Estimated price elasticity (negative for normal goods)
            learning_rate: How aggressively to adjust prices
        """
        self.base_price = base_price
        self.min_price = min_price
        self.max_price = max_price
        self.elasticity = elasticity
        self.learning_rate = learning_rate
        self.price_history = []
        self.demand_history = []

    def calculate_optimal_price(self, current_demand: float, revenue_target: float) -> float:
        """
        Calculate price adjustment based on:
        - Current demand vs expected demand
        - Progress toward revenue target
        - Price elasticity model
        """
        if len(self.price_history) > 0 and len(self.demand_history) > 0:
            last_price = self.price_history[-1]
            elasticity_observed = self._estimate_elasticity()
            
            # Blend model and observed elasticity
            effective_elasticity = (elasticity_observed + self.elasticity)/2 if elasticity_observed else self.elasticity
            
            # Calculate revenue-optimal price using elasticity model
            optimal_price = last_price * (1 + ((1/effective_elasticity) * self.learning_rate))
            
            # Apply revenue target pressure
            target_adjustment = 1 + (0.01 * np.log(max(1, revenue_target/current_demand)))
            new_price = optimal_price * target_adjustment
        else:
            new_price = self.base_price
            
        return np.clip(new_price, self.min_price, self.max_price)

    def _estimate_elasticity(self) -> Optional[float]:
        """Calculate observed elasticity from historical data"""
        if len(self.price_history) < 2 or len(self.demand_history) < 2:
            return None
            
        price_changes = np.diff(self.price_history)
        demand_changes = np.diff(self.demand_history)
        
        # Percent change calculations
        price_pct = price_changes / self.price_history[:-1] 
        demand_pct = demand_changes / self.demand_history[:-1]
        
        try:
            elasticity = np.mean(demand_pct / price_pct)
            return elasticity
        except:
            return None

    def update_history(self, price: float, demand: float):
        """Record latest price and demand data"""
        self.price_history.append(price)
        self.demand_history.append(demand)
        if len(self.price_history) > 10:  # Keep rolling window
            self.price_history.pop(0)
            self.demand_history.pop(0)


def optimize_product_portfolio_prices(db_query_fn, products: List[Dict], target_revenue: float) -> Dict[str, float]:
    """
    Optimize prices across product portfolio considering:
    - Cross-product elasticity 
    - Revenue targets
    - Inventory levels
    Returns dict of product_id: new_price
    """
    optimized_prices = {}
    total_current_revenue = sum(p['price']*p['demand'] for p in products)
    
    for product in products:
        optimizer = PricingOptimizer(
            base_price=product['price'],
            min_price=product['min_price'],
            max_price=product['max_price'],
            elasticity=product.get('elasticity', -1.5)
        )
        
        new_price = optimizer.calculate_optimal_price(
            current_demand=product['demand'],
            revenue_target=target_revenue * (product['revenue_share'] if 'revenue_share' in product else 1/len(products))
        )
        
        optimized_prices[product['id']] = round(new_price, 2)
        optimizer.update_history(new_price, product['demand'])
    
    return optimized_prices
