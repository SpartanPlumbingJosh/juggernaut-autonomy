import logging
from typing import Dict
from core.database import query_db

class ProductDeliveryService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def deliver_product(
        self,
        customer_email: str,
        product_id: str,
        order_details: Dict
    ) -> Dict:
        """Deliver purchased product to customer"""
        try:
            # Generate license/key if needed
            license_key = self._generate_license_key()
            
            # Send download link via email
            await self._send_delivery_email(
                customer_email,
                product_id,
                license_key
            )

            # Record delivery in database
            await query_db(
                f"""
                INSERT INTO product_deliveries (
                    order_id, product_id, customer_email,
                    license_key, delivered_at, status
                ) VALUES (
                    '{order_details['order_id']}', 
                    '{product_id}',
                    '{customer_email}',
                    '{license_key}',
                    NOW(),
                    'delivered'
                )
                """
            )

            self.logger.info(f"Delivered product {product_id} to {customer_email}")
            return {
                'success': True,
                'license_key': license_key
            }
        except Exception as e:
            self.logger.error(f"Delivery failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _generate_license_key(self) -> str:
        """Generate a random license key"""
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(16))

    async def _send_delivery_email(
        self,
        email: str,
        product_id: str,
        license_key: str
    ) -> None:
        """Send product delivery email"""
        # TODO: Implement actual email sending
        print(f"Sending download link to {email} for product {product_id}")
