import os
from typing import Dict
from core.database import query_db
from core.logging import logger
from core.email_service import send_service_email

class ServiceFulfillment:
    async def fulfill_service(self, service_data: Dict) -> None:
        try:
            # Register the service activation
            await query_db(
                f"""
                INSERT INTO service_activations (
                    id, customer_email, product_id,
                    status, activated_at, expires_at
                ) VALUES (
                    gen_random_uuid(),
                    '{service_data['customer_email']}',
                    '{service_data['product_id']}',
                    'active',
                    NOW(),
                    NOW() + INTERVAL '1 year'
                )
                """
            )
            
            # Send welcome/access email
            await send_service_email(
                to=service_data['customer_email'],
                template='service_welcome',
                context={
                    'product_name': service_data['product_name'],
                    'access_link': self._generate_access_link(service_data)
                }
            )
            
            logger.info(f"Service fulfilled for {service_data['customer_email']}")
            
        except Exception as e:
            logger.error(f"Service fulfillment failed: {str(e)}")
            raise

    def _generate_access_link(self, service_data: Dict) -> str:
        base_url = os.getenv('BASE_URL')
        product_slug = service_data['product_name'].lower().replace(' ', '-')
        return f"{base_url}/access/{product_slug}/{service_data['product_id']}"
