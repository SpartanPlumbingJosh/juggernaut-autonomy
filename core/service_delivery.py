from typing import Dict, Any
from datetime import datetime, timedelta
import random

class ServiceDelivery:
    def __init__(self):
        self.services = {
            "basic": {
                "price": 1000,  # in cents
                "duration": timedelta(days=30),
                "features": ["feature1", "feature2"]
            },
            "premium": {
                "price": 2000,
                "duration": timedelta(days=30),
                "features": ["feature1", "feature2", "feature3"]
            }
        }

    async def deliver_service(self, plan: str, user_id: str) -> Dict[str, Any]:
        if plan not in self.services:
            return {"error": "Invalid service plan"}
            
        service = self.services[plan]
        delivery_id = f"delivery_{random.randint(1000, 9999)}"
        
        return {
            "delivery_id": delivery_id,
            "user_id": user_id,
            "plan": plan,
            "price": service["price"],
            "start_date": datetime.utcnow(),
            "end_date": datetime.utcnow() + service["duration"],
            "features": service["features"]
        }
