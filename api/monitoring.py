"""
Revenue System Monitoring - Tracks performance and scaling metrics
"""
from datetime import datetime, timedelta
from typing import Dict, Any
import logging
import psutil
import requests

from core.database import query_db

class RevenueMonitor:
    def __init__(self):
        self.last_check = datetime.utcnow()
        
    async def check_system_health(self) -> Dict[str, Any]:
        """Check all critical system metrics"""
        now = datetime.utcnow()
        
        # System resources
        cpu = psutil.cpu_percent()
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        
        # Revenue throughput
        hour_ago = now - timedelta(hours=1)
        res = await query_db(f"""
            SELECT COUNT(*) as tx_count, 
                   SUM(amount_cents) as revenue_cents
            FROM revenue_events
            WHERE recorded_at >= '{hour_ago.isoformat()}'
            AND event_type = 'revenue'
        """)
        
        row = res.get("rows", [{}])[0]
        hourly_tx = row.get("tx_count", 0)
        hourly_revenue = row.get("revenue_cents", 0) / 100
        
        # External service status
        services = {
            "payment_processor": self._check_service("https://api.stripe.com"),
            "database": self._check_database(),
            "api": self._check_api()
        }
        
        return {
            "timestamp": now.isoformat(),
            "system": {
                "cpu": cpu,
                "memory": memory,
                "disk": disk
            },
            "throughput": {
                "transactions_last_hour": hourly_tx,
                "revenue_last_hour": hourly_revenue
            },
            "services": services
        }
        
    def _check_service(self, url: str) -> bool:
        try:
            return requests.get(url, timeout=3).status_code < 500
        except:
            return False
            
    async def _check_database(self) -> bool:
        try:
            res = await query_db("SELECT 1")
            return bool(res)
        except:
            return False
            
    def _check_api(self) -> bool:
        return self._check_service("http://localhost:8000/health")
