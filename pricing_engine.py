from typing import Dict, Any
import numpy as np
from datetime import datetime, timedelta

class PricingEngine:
    def __init__(self):
        self.price_history = {}
        self.demand_factors = {}

    def calculate_optimal_price(
        self,
        product_id: str,
        base_price: float,
        demand_data: Dict[str, Any]
    ) -> float:
        """Calculate dynamic price based on demand and history"""
        # Get historical price performance
        history = self.price_history.get(product_id, [])
        
        # Calculate demand factor (0.8-1.2 range)
        demand_factor = min(max(
            0.8, 
            self._calculate_demand_factor(demand_data)
        ), 1.2)
        
        # Apply exponential smoothing to price changes
        if history:
            last_price = history[-1]["price"]
            smoothing_factor = 0.3
            new_price = (smoothing_factor * (base_price * demand_factor)) + \
                       ((1 - smoothing_factor) * last_price)
        else:
            new_price = base_price * demand_factor
        
        # Record this price decision
        self._record_price(product_id, new_price, demand_data)
        
        return round(new_price, 2)

    def _calculate_demand_factor(self, demand_data: Dict[str, Any]) -> float:
        """Calculate demand factor from metrics"""
        conversion_rate = demand_data.get("conversion_rate", 1.0)
        inventory_level = demand_data.get("inventory_level", 1.0)
        competitor_price = demand_data.get("competitor_price", 1.0)
        
        # Simple weighted average of factors
        return (conversion_rate * 0.5) + \
               (1/inventory_level * 0.3) + \
               (1/competitor_price * 0.2)

    def _record_price(
        self,
        product_id: str,
        price: float,
        demand_data: Dict[str, Any]
    ) -> None:
        """Record price decision in history"""
        if product_id not in self.price_history:
            self.price_history[product_id] = []
            
        self.price_history[product_id].append({
            "timestamp": datetime.utcnow().isoformat(),
            "price": price,
            "demand_data": demand_data
        })
