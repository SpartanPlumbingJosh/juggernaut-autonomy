"""
Usage-based metering system.
Tracks usage and calculates charges based on consumption.
"""

from typing import Dict, List
from datetime import datetime

class UsageMeter:
    """Tracks and manages usage-based billing"""
    
    def __init__(self):
        self.usage_records = {}
        
    def record_usage(self, customer_id: str, metric: str, value: float, timestamp: datetime = None):
        """Record usage for a customer"""
        if customer_id not in self.usage_records:
            self.usage_records[customer_id] = []
            
        self.usage_records[customer_id].append({
            "metric": metric,
            "value": value,
            "timestamp": timestamp or datetime.utcnow()
        })
        
    def get_usage(self, customer_id: str, metric: str, start_date: datetime, end_date: datetime) -> float:
        """Get total usage for a customer between dates"""
        if customer_id not in self.usage_records:
            return 0.0
            
        total = sum(
            record["value"]
            for record in self.usage_records[customer_id]
            if record["metric"] == metric and
            start_date <= record["timestamp"] <= end_date
        )
        return total
        
    def calculate_charges(self, customer_id: str, pricing_plan: Dict) -> float:
        """Calculate charges based on usage and pricing plan"""
        charges = 0.0
        for metric, tiers in pricing_plan.items():
            usage = self.get_usage(customer_id, metric, pricing_plan["start_date"], pricing_plan["end_date"])
            for tier in tiers:
                if usage > tier["threshold"]:
                    charges += tier["price"] * (usage - tier["threshold"])
        return charges
