"""
Product Delivery System - Handles automated fulfillment of digital products/services.
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProductDelivery:
    def __init__(self):
        self.delivery_methods = {
            'email': self._deliver_via_email,
            'api': self._deliver_via_api,
            'download': self._deliver_via_download
        }

    async def deliver_product(
        self,
        product_data: Dict[str, Any],
        customer_data: Dict[str, Any],
        payment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deliver product based on its type and delivery method.
        Returns delivery status and details.
        """
        delivery_method = product_data.get('delivery_method', 'email')
        handler = self.delivery_methods.get(delivery_method, self._deliver_via_email)

        try:
            result = await handler(product_data, customer_data, payment_data)
            result['status'] = 'delivered'
            result['timestamp'] = datetime.now(timezone.utc).isoformat()
            return result
        except Exception as e:
            logger.error(f"Delivery failed: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

    async def _deliver_via_email(
        self,
        product_data: Dict[str, Any],
        customer_data: Dict[str, Any],
        payment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deliver product via email"""
        # In production, integrate with email service
        return {
            'method': 'email',
            'email_sent_to': customer_data['email'],
            'product_id': product_data['id']
        }

    async def _deliver_via_api(
        self,
        product_data: Dict[str, Any],
        customer_data: Dict[str, Any],
        payment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deliver product via API call"""
        # In production, make API call to fulfillment service
        return {
            'method': 'api',
            'api_endpoint': product_data.get('api_endpoint'),
            'customer_id': customer_data.get('id'),
            'product_id': product_data['id']
        }

    async def _deliver_via_download(
        self,
        product_data: Dict[str, Any],
        customer_data: Dict[str, Any],
        payment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate download link for product"""
        # In production, generate secure download link
        return {
            'method': 'download',
            'download_url': f"https://downloads.example.com/{product_data['id']}",
            'expires_at': (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            'product_id': product_data['id']
        }
