import logging
from typing import Dict, Any
import requests
import os
import time

logger = logging.getLogger(__name__)

class MonitoringService:
    def __init__(self):
        self.webhook_url = os.getenv("MONITORING_WEBHOOK_URL")
        self.retry_count = 3
        self.retry_delay = 5

    def log_error(self, error_data: Dict[str, Any]) -> bool:
        for attempt in range(self.retry_count):
            try:
                response = requests.post(
                    self.webhook_url,
                    json=error_data,
                    timeout=10
                )
                response.raise_for_status()
                return True
            except Exception as e:
                logger.warning(f"Error reporting attempt {attempt + 1} failed: {str(e)}")
                time.sleep(self.retry_delay)
        return False

    def log_heartbeat(self, service_name: str) -> bool:
        for attempt in range(self.retry_count):
            try:
                response = requests.post(
                    self.webhook_url,
                    json={
                        "service": service_name,
                        "timestamp": time.time(),
                        "type": "heartbeat"
                    },
                    timeout=10
                )
                response.raise_for_status()
                return True
            except Exception as e:
                logger.warning(f"Heartbeat attempt {attempt + 1} failed: {str(e)}")
                time.sleep(self.retry_delay)
        return False
