"""
Digital Delivery Service - Automated fulfillment of digital products.

Handles:
- File downloads
- License key generation
- API access provisioning
- Email notifications
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import smtplib
from email.mime.text import MIMEText
from core.database import query_db

class DigitalDeliveryService:
    """Automated digital product fulfillment."""
    
    async def fulfill_order(self, product_id: str, customer_id: Optional[str], metadata: Dict[str, Any]) -> None:
        """Fulfill an order by delivering the digital product."""
        try:
            # Get product details
            product = await self._get_product(product_id)
            if not product:
                logging.error(f"Product not found: {product_id}")
                return
                
            # Generate license key if required
            license_key = None
            if product.get('requires_license'):
                license_key = str(uuid.uuid4())
                await self._store_license(product_id, license_key, customer_id)
                
            # Deliver via appropriate method
            delivery_method = product.get('delivery_method')
            
            if delivery_method == 'download':
                await self._send_download_link(product, customer_id, license_key, metadata)
            elif delivery_method == 'api':
                await self._provision_api_access(product, customer_id, license_key, metadata)
            else:
                logging.error(f"Unknown delivery method: {delivery_method}")
                
        except Exception as e:
            logging.error(f"Failed to fulfill order: {str(e)}")

    async def _get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get product details from database."""
        result = await query_db(f"""
            SELECT * FROM digital_products 
            WHERE id = '{product_id.replace("'", "''")}'
        """)
        return result.get('rows', [{}])[0] if result else None

    async def _store_license(self, product_id: str, license_key: str, customer_id: Optional[str]) -> None:
        """Store generated license key."""
        await query_db(f"""
            INSERT INTO product_licenses (
                id, product_id, license_key, 
                customer_id, created_at, expires_at
            ) VALUES (
                gen_random_uuid(),
                '{product_id.replace("'", "''")}',
                '{license_key.replace("'", "''")}',
                {'NULL' if not customer_id else f"'{customer_id.replace("'", "''")}'"},
                NOW(),
                NOW() + INTERVAL '1 year'
            )
        """)

    async def _send_download_link(self, product: Dict[str, Any], 
                                customer_id: Optional[str],
                                license_key: Optional[str],
                                metadata: Dict[str, Any]) -> None:
        """Send download link via email."""
        email = metadata.get('email')
        if not email:
            logging.error("No email provided for download delivery")
            return
            
        download_url = product.get('download_url')
        if not download_url:
            logging.error(f"No download URL configured for product {product.get('id')}")
            return
            
        message = f"""
        Thank you for your purchase!
        
        Product: {product.get('name')}
        
        Download URL: {download_url}
        {f"License Key: {license_key}" if license_key else ""}
        
        This URL will be valid for 30 days.
        """
        
        self._send_email(
            to_email=email,
            subject=f"Your download: {product.get('name')}",
            body=message
        )

    async def _provision_api_access(self, product: Dict[str, Any],
                                  customer_id: Optional[str],
                                  license_key: str,
                                  metadata: Dict[str, Any]) -> None:
        """Provision API access for the customer."""
        if not license_key:
            license_key = str(uuid.uuid4())
            
        # Store API credentials
        await query_db(f"""
            INSERT INTO api_credentials (
                id, product_id, license_key, 
                customer_id, created_at, expires_at
            ) VALUES (
                gen_random_uuid(),
                '{product.get('id').replace("'", "''")}',
                '{license_key.replace("'", "''")}',
                {'NULL' if not customer_id else f"'{customer_id.replace("'", "''")}'"},
                NOW(),
                NOW() + INTERVAL '1 year'
            )
        """)
        
        email = metadata.get('email')
        if email and product.get('send_api_credentials'):
            message = f"""
            Your API access has been provisioned!
            
            Product: {product.get('name')}
            API Endpoint: {product.get('api_endpoint')}
            License Key: {license_key}
            """
            
            self._send_email(
                to_email=email,
                subject=f"API Access: {product.get('name')}",
                body=message
            )

    def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send notification email."""
        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = 'noreply@example.com'
            msg['To'] = to_email
            
            # In production, configure proper SMTP settings
            with smtplib.SMTP('localhost') as server:
                server.send_message(msg)
            return True
        except Exception as e:
            logging.error(f"Failed to send email: {str(e)}")
            return False
