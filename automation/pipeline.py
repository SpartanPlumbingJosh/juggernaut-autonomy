"""
Automation Pipeline - End-to-end system for market discovery, value delivery, 
and payment processing with error handling and monitoring.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from core.database import query_db
from core.market_discovery import discover_market_opportunities
from core.value_delivery import generate_listings, fulfill_orders
from core.payment_processor import process_payments
from core.error_handler import handle_errors, notify_alert
from core.monitoring import monitor_system_health

class AutomationPipeline:
    """Orchestrates the end-to-end automation workflow."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.last_run = None
        self.error_count = 0
        self.max_errors_before_alert = 5
        
    async def run_pipeline(self):
        """Execute the full automation cycle."""
        try:
            # System health check
            if not await monitor_system_health():
                self.logger.error("System health check failed")
                return False
                
            # Market Discovery Phase
            opportunities = await discover_market_opportunities()
            if not opportunities:
                self.logger.warning("No market opportunities found")
                return False
                
            # Value Delivery Phase
            listings = await generate_listings(opportunities)
            if not listings:
                self.logger.error("Failed to generate listings")
                return False
                
            fulfillment_results = await fulfill_orders(listings)
            if not fulfillment_results.get("success"):
                self.logger.error("Order fulfillment failed")
                return False
                
            # Payment Processing Phase
            payment_results = await process_payments(fulfillment_results["completed_orders"])
            if not payment_results.get("success"):
                self.logger.error("Payment processing failed")
                return False
                
            # Update last run and reset error count
            self.last_run = datetime.utcnow()
            self.error_count = 0
            return True
            
        except Exception as e:
            self.error_count += 1
            await handle_errors(e)
            
            if self.error_count >= self.max_errors_before_alert:
                await notify_alert(f"Critical system failure: {str(e)}")
                
            return False
            
    async def run_continuously(self, interval_minutes: int = 60):
        """Run pipeline on a continuous loop."""
        while True:
            start_time = datetime.utcnow()
            
            success = await self.run_pipeline()
            if not success:
                self.logger.warning("Pipeline run failed")
                
            # Calculate sleep time accounting for execution duration
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            sleep_time = max(0, interval_minutes * 60 - elapsed)
            
            await asyncio.sleep(sleep_time)

async def start_pipeline():
    """Initialize and start the automation pipeline."""
    pipeline = AutomationPipeline()
    await pipeline.run_continuously()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_pipeline())
