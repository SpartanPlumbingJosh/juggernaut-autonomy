import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
import os
import requests

logger = logging.getLogger(__name__)

class DeliveryService:
    def __init__(self):
        self.api_key = os.getenv("DELIVERY_API_KEY")
        self.base_url = os.getenv("DELIVERY_BASE_URL")

    def initiate_delivery(self, order_id: str, user_id: str) -> Optional[Dict]:
        try:
            response = requests.post(
                f"{self.base_url}/deliveries",
                json={
                    "order_id": order_id,
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat()
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to initiate delivery: {str(e)}")
            return None

    def check_delivery_status(self, delivery_id: str) -> Optional[Dict]:
        try:
            response = requests.get(
                f"{self.base_url}/deliveries/{delivery_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to check delivery status: {str(e)}")
            return None
