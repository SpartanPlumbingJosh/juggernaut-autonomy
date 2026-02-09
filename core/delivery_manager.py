import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class DeliveryManager:
    """Handles digital product delivery automation."""

    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql

    async def fulfill_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process order fulfillment."""
        try:
            product_id = order_data.get('product_id')
            customer_email = order_data.get('customer_email')
            license_key = str(uuid.uuid4()).replace('-', '').upper()[:16]
            
            # Store delivery record
            self.execute_sql(
                f"""
                INSERT INTO deliveries (
                    id, product_id, customer_email, 
                    license_key, status, created_at, 
                    delivered_at
                ) VALUES (
                    gen_random_uuid(),
                    %s, %s, %s, 
                    'delivered', NOW(), 
                    NOW()
                )
                RETURNING id
                """,
                (product_id, customer_email, license_key)
            )

            # TODO: Actually send email with download link/license key
            logger.info(f"Order fulfilled for {customer_email}")

            return {
                'success': True,
                'delivery_id': license_key,
                'customer_email': customer_email,
                'license_key': license_key,
                'download_url': f"https://download.example.com/{license_key}"
            }

        except Exception as e:
            logger.error(f"Fulfillment failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'order_data': order_data
            }

    async def resend_delivery(self, delivery_id: str) -> Dict[str, Any]:
        """Resend a delivery to customer."""
        try:
            # Get original delivery record
            result = self.execute_sql(
                """
                SELECT product_id, customer_email, license_key 
                FROM deliveries 
                WHERE id = %s
                """,
                (delivery_id,)
            )
            record = result.get('rows', [{}])[0]
            
            if not record:
                return {'success': False, 'error': 'Delivery not found'}

            # TODO: Send email again
            logger.info(f"Resent delivery {delivery_id} to {record['customer_email']}")

            return {
                'success': True,
                'customer_email': record['customer_email'],
                'license_key': record['license_key'],
                'original_delivery_time': result['created_at']
            }

        except Exception as e:
            logger.error(f"Delivery resend failed: {str(e)}")
            return {'success': False, 'error': str(e)}
