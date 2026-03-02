"""Background worker for automated service fulfillment."""
import asyncio
import logging
from datetime import datetime, timedelta

from core.database import query_db, execute_db
from services.service_manager import ServiceManager

logger = logging.getLogger(__name__)

async def process_pending_fulfillments():
    """Process pending orders every minute."""
    manager = ServiceManager()
    while True:
        try:
            logger.info("Checking for pending fulfillments...")
            result = await query_db(
                """
                SELECT id FROM service_fulfillments
                WHERE status = 'pending'
                LIMIT 10
                """
            )
            
            for row in result.get('rows', []):
                fulfillment_id = row['id']
                logger.info(f"Processing fulfillment {fulfillment_id}")
                await manager.fulfill_order(fulfillment_id)
                
        except Exception as e:
            logger.error(f"Fulfillment processing error: {str(e)}")
        
        await asyncio.sleep(60)  # Run every minute

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(process_pending_fulfillments())
