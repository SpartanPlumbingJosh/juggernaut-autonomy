"""
Production deployment configuration for Revenue Tracking System.

Features:
- Scheduled execution of revenue tracking tasks
- Health monitoring and alerts
- Automated failover
- Webhook integration for external systems
"""

import os
import time
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
import requests
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("revenue_deploy.log"),
        logging.StreamHandler()
    ]
)

class RevenueDeployer:
    """Production deployment manager for revenue tracking system."""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.last_run = {}
        self.health_checks = {}
        self.webhook_urls = os.getenv("REVENUE_WEBHOOKS", "").split(",")
        
    def schedule_tasks(self):
        """Schedule recurring revenue tracking tasks."""
        while True:
            try:
                now = datetime.utcnow()
                
                # Run summary every 5 minutes
                if not self.last_run.get("summary") or now - self.last_run["summary"] >= timedelta(minutes=5):
                    self.executor.submit(self.run_summary)
                    self.last_run["summary"] = now
                
                # Run transactions sync every 15 minutes
                if not self.last_run.get("transactions") or now - self.last_run["transactions"] >= timedelta(minutes=15):
                    self.executor.submit(self.run_transactions)
                    self.last_run["transactions"] = now
                
                # Run charts update every hour
                if not self.last_run.get("charts") or now - self.last_run["charts"] >= timedelta(hours=1):
                    self.executor.submit(self.run_charts)
                    self.last_run["charts"] = now
                
                # Health check every minute
                self.run_health_checks()
                
                time.sleep(60)
                
            except Exception as e:
                logging.error(f"Scheduling error: {str(e)}")
                time.sleep(300)  # Wait 5 minutes before retrying
    
    def run_summary(self):
        """Execute revenue summary task."""
        try:
            from api.revenue_api import handle_revenue_summary
            result = handle_revenue_summary()
            self.notify_webhooks("summary", result)
            logging.info("Revenue summary completed")
        except Exception as e:
            logging.error(f"Summary task failed: {str(e)}")
            self.health_checks["summary"] = {"status": "failed", "error": str(e)}
    
    def run_transactions(self):
        """Execute transactions sync task."""
        try:
            from api.revenue_api import handle_revenue_transactions
            result = handle_revenue_transactions({})
            self.notify_webhooks("transactions", result)
            logging.info("Transactions sync completed")
        except Exception as e:
            logging.error(f"Transactions task failed: {str(e)}")
            self.health_checks["transactions"] = {"status": "failed", "error": str(e)}
    
    def run_charts(self):
        """Execute charts update task."""
        try:
            from api.revenue_api import handle_revenue_charts
            result = handle_revenue_charts({"days": "30"})
            self.notify_webhooks("charts", result)
            logging.info("Charts update completed")
        except Exception as e:
            logging.error(f"Charts task failed: {str(e)}")
            self.health_checks["charts"] = {"status": "failed", "error": str(e)}
    
    def run_health_checks(self):
        """Run system health checks."""
        checks = {
            "database": self.check_database(),
            "api": self.check_api(),
            "tasks": self.check_tasks()
        }
        self.health_checks.update(checks)
        
        if any(c["status"] == "failed" for c in checks.values()):
            self.notify_webhooks("health", checks)
            logging.warning("Health check failures detected")
    
    def check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            from core.database import query_db
            query_db("SELECT 1")
            return {"status": "ok"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def check_api(self) -> Dict[str, Any]:
        """Check API availability."""
        try:
            from api.revenue_api import route_request
            result = route_request("/revenue/summary", "GET", {})
            if result.get("statusCode") == 200:
                return {"status": "ok"}
            return {"status": "failed", "error": f"API returned {result.get('statusCode')}"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def check_tasks(self) -> Dict[str, Any]:
        """Check task execution status."""
        status = "ok"
        errors = []
        for task, check in self.health_checks.items():
            if check.get("status") == "failed":
                status = "failed"
                errors.append(f"{task}: {check.get('error')}")
        return {"status": status, "errors": errors}
    
    def notify_webhooks(self, event_type: str, data: Dict[str, Any]):
        """Notify configured webhooks of system events."""
        payload = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        for url in self.webhook_urls:
            if not url:
                continue
            try:
                requests.post(url, json=payload, timeout=5)
            except Exception as e:
                logging.error(f"Webhook notification failed to {url}: {str(e)}")

def start_deployment():
    """Start the revenue deployment system."""
    deployer = RevenueDeployer()
    deployer.schedule_tasks()

if __name__ == "__main__":
    start_deployment()
