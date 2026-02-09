"""
Automated fulfillment system that handles:
- Digital product delivery
- License key generation
- Access provisioning
- Auto-resends
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FulfillmentService:
    def __init__(self):
        self.digital_products = {
            "basic": {
                "delivery_method": "email",
                "download_url": f"{os.getenv('CDN_BASE_URL')}/products/basic",
                "license_keys": self._generate_license_keys
            },
            "pro": {
                "delivery_method": "api",
                "api_endpoint": f"{os.getenv('API_BASE_URL')}/activate",
                "license_keys": self._generate_license_keys
            }
        }

    async def fulfill_order(self, order_id: str, product_id: str, customer_email: str) -> Dict[str, Any]:
        """Process order fulfillment"""
        product = self.digital_products.get(product_id.lower())
        if not product:
            raise ValueError(f"Product {product_id} not found")
        
        try:
            # Generate license key(s)
            license_keys = await product['license_keys'](quantity=1)
            
            # Record fulfillment
            fulfillment_id = str(uuid.uuid4())
            fulfillment_data = {
                "order_id": order_id,
                "product_id": product_id,
                "customer_email": customer_email,
                "license_keys": license_keys,
                "fulfilled_at": datetime.utcnow().isoformat(),
                "status": "completed"
            }
            
            # Trigger delivery based on method
            if product['delivery_method'] == 'email':
                await self._send_delivery_email(customer_email, product, license_keys)
            elif product['delivery_method'] == 'api':
                await self._provision_api_access(customer_email, product, license_keys)
                
            return {
                "success": True,
                "fulfillment_id": fulfillment_id,
                "license_keys": license_keys
            }
            
        except Exception as e:
            logger.error(f"Fulfillment failed for order {order_id}: {str(e)}")
            raise ValueError(f"Fulfillment failed: {str(e)}")

    async def _generate_license_keys(self, quantity: int = 1) -> List[str]:
        """Generate unique license keys"""
        return [str(uuid.uuid4()).replace("-", "").upper()[:16] for _ in range(quantity)]

    async def _send_delivery_email(self, email: str, product: Dict, license_keys: List[str]) -> bool:
        """Send product delivery email"""
        # Implementation would use email service like SendGrid
        logger.info(f"Sent delivery email to {email} with license keys")
        return True

    async def _provision_api_access(self, email: str, product: Dict, license_keys: List[str]) -> bool:
        """Provision API access credentials"""
        # Implementation would call access management system
        logger.info(f"Provisioned API access for {email}")
        return True

    async def resend_fulfillment(self, fulfillment_id: str) -> Dict[str, Any]:
        """Resend fulfillment if delivery failed"""
        # Implementation would look up original fulfillment
        # and reattempt delivery
        logger.info(f"Resending fulfillment {fulfillment_id}")
        return {"success": True}
