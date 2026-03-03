import logging
from typing import Dict
from core.database import query_db

logger = logging.getLogger(__name__)

class ServiceDelivery:
    """Handle automated service delivery."""
    
    async def deliver_service(self, service_type: str, metadata: Dict) -> None:
        """Deliver service based on type."""
        try:
            if service_type == "digital_product":
                await self._deliver_digital_product(metadata)
            elif service_type == "subscription":
                await self._deliver_subscription(metadata)
            else:
                logger.warning(f"Unknown service type: {service_type}")
        except Exception as e:
            logger.error(f"Service delivery failed: {str(e)}")
            raise
    
    async def _deliver_digital_product(self, metadata: Dict) -> None:
        """Deliver digital product."""
        # Generate download link
        download_url = f"https://download.example.com/{metadata.get('product_id')}"
        
        # Update metadata with delivery info
        await query_db(f"""
            UPDATE revenue_events
            SET metadata = metadata || '{"download_url": "{download_url}"}'::jsonb
            WHERE id = '{metadata.get("payment_id")}'
        """)
        
        logger.info(f"Digital product delivered: {download_url}")
    
    async def _deliver_subscription(self, metadata: Dict) -> None:
        """Activate subscription."""
        # Create subscription record
        await query_db(f"""
            INSERT INTO subscriptions (
                id, user_id, plan_id, status,
                start_date, end_date, created_at
            ) VALUES (
                gen_random_uuid(),
                '{metadata.get("user_id")}',
                '{metadata.get("plan_id")}',
                'active',
                NOW(),
                NOW() + INTERVAL '1 month',
                NOW()
            )
        """)
        
        logger.info(f"Subscription activated for user: {metadata.get('user_id')}")
