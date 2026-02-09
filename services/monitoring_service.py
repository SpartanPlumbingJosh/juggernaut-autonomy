"""
System monitoring and failover service.
Continuously checks system health and triggers recovery actions.
"""

import time
import logging
from typing import Dict, Any

class SystemMonitor:
    """Monitors critical services and triggers alerts/recovery."""
    
    def __init__(self, db_executor, alert_handler):
        self.db = db_executor
        self.alert_handler = alert_handler
        self.checks = [
            self._check_database,
            self._check_payment_processor,
            self._check_delivery_service
        ]
        
    async def run_checks(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {}
        for check in self.checks:
            try:
                results[check.__name__] = await check()
            except Exception as e:
                results[check.__name__] = {
                    "status": "error",
                    "error": str(e)
                }
        return results
        
    async def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            result = await self.db("SELECT 1")
            return {"status": "healthy"}
        except Exception as e:
            await self.alert_handler("database_down", str(e))
            return {"status": "unhealthy", "error": str(e)}
            
    async def _check_payment_processor(self) -> Dict[str, Any]:
        """Check Stripe API connectivity."""
        try:
            import stripe
            stripe.PaymentIntent.list(limit=1)
            return {"status": "healthy"}
        except Exception as e:
            await self.alert_handler("payment_processor_down", str(e))
            return {"status": "unhealthy", "error": str(e)}
            
    async def _check_delivery_service(self) -> Dict[str, Any]:
        """Check delivery service queue."""
        try:
            result = await self.db(
                "SELECT COUNT(*) as pending FROM orders WHERE status = 'pending'"
            )
            pending = result.get("rows", [{}])[0].get("pending", 0)
            
            if pending > 10:
                await self.alert_handler("delivery_backlog", f"{pending} pending orders")
                return {"status": "warning", "pending": pending}
            return {"status": "healthy", "pending": pending}
        except Exception as e:
            return {"status": "error", "error": str(e)}


async def start_monitoring(db_executor, alert_handler, interval: int = 300) -> None:
    """Start continuous monitoring loop."""
    monitor = SystemMonitor(db_executor, alert_handler)
    while True:
        try:
            await monitor.run_checks()
        except Exception as e:
            logging.error(f"Monitoring failed: {str(e)}")
        time.sleep(interval)
