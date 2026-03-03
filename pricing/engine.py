"""
Dynamic pricing engine that optimizes prices based on demand, inventory, and performance.
"""
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class PricingEngine:
    def __init__(self, base_price: float, min_price: float, max_price: float):
        self.base_price = base_price
        self.min_price = min_price
        self.max_price = max_price
        self.price = base_price
        self.last_adjusted = datetime.now()
        
    def calculate_demand_factor(self, transactions: List[Dict]) -> float:
        """Calculate demand factor based on recent transaction volume"""
        if not transactions:
            return 1.0
            
        recent_hours = 24
        cutoff = datetime.now() - timedelta(hours=recent_hours)
        recent_txns = [t for t in transactions if t.get('recorded_at') >= cutoff]
        
        if len(recent_txns) < 10:  # Not enough data
            return 1.0
            
        avg_daily = len(recent_txns) / (recent_hours / 24)
        return min(2.0, max(0.5, avg_daily / 100))  # Scale between 0.5-2.0
    
    def calculate_conversion_factor(self, transactions: List[Dict]) -> float:
        """Calculate conversion impact factor"""
        if not transactions:
            return 1.0
            
        # Get conversion rate from last 100 transactions
        sample = transactions[-100:]
        views = sum(t.get('metadata', {}).get('views', 1) for t in sample)
        purchases = len([t for t in sample if t.get('event_type') == 'revenue'])
        
        if views < 10 or purchases == 0:
            return 1.0
            
        conversion_rate = purchases / views
        # Normalize to target 5% conversion rate
        return min(2.0, max(0.5, conversion_rate / 0.05))
    
    def adjust_price(self, transactions: List[Dict], inventory_level: float) -> float:
        """Calculate optimized price based on market factors"""
        if datetime.now() - self.last_adjusted < timedelta(hours=1):
            return self.price
            
        demand_factor = self.calculate_demand_factor(transactions)
        conversion_factor = self.calculate_conversion_factor(transactions)
        
        # Inventory factor (1.0 when 50% remaining, scales up as inventory decreases)
        inventory_factor = 1.0 + (0.5 - inventory_level) * 2  
        
        new_price = self.base_price * demand_factor * conversion_factor * inventory_factor
        new_price = min(self.max_price, max(self.min_price, new_price))
        
        # Smooth price changes
        self.price = self.price * 0.7 + new_price * 0.3
        self.last_adjusted = datetime.now()
        
        return round(self.price, 2)
