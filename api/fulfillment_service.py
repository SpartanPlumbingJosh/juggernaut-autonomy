"""
Digital product fulfillment service.
Generates licenses, download links, or triggers services.
"""
import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from core.database import query_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FulfillmentService:
    """Handles product delivery after payment."""
    
    @staticmethod
    async def fulfill_digital_product(
        product_id: str,
        customer_email: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Generate digital product access."""
        try:
            # Generate license key
            license_key = str(uuid.uuid4())
            expires_at = datetime.utcnow() + timedelta(days=365)
            
            # Record fulfillment
            await query_db(f"""
                INSERT INTO product_fulfillments (
                    id, product_id, customer_email, 
                    license_key, expires_at, 
                    created_at, metadata
                ) VALUES (
                    gen_random_uuid(),
                    '{product_id}',
                    '{customer_email}',
                    '{license_key}',
                    '{expires_at.isoformat()}',
                    NOW(),
                    '{json.dumps(metadata or {})}'::jsonb
                )
            """)
            
            # Generate download link (in real implementation, this would be signed)
            download_url = f"https://download.example.com/{license_key}"
            
            # TODO: Send email with download instructions
            
            logger.info(f"Fulfilled product {product_id} for {customer_email}")
            return {
                "success": True,
                "download_url": download_url,
                "license_key": license_key,
                "expires_at": expires_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Fulfillment failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
