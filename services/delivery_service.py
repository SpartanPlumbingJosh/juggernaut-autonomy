"""
Automated delivery service for digital products and services.
"""
import os
import logging
from typing import Dict, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import aiohttp

logger = logging.getLogger(__name__)

class DeliveryService:
    def __init__(self, config: Dict[str, Any]):
        self.smtp_host = config.get("smtp_host")
        self.smtp_port = config.get("smtp_port", 587)
        self.smtp_user = config.get("smtp_user")
        self.smtp_pass = config.get("smtp_pass")
        self.from_email = config.get("from_email")
        
    async def deliver_product(self, product_id: str, customer_email: str, 
                             metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Handle automated delivery of different product types."""
        try:
            # Dispatch based on product type
            if product_id.startswith("dig_"):
                return await self._deliver_digital_product(product_id, customer_email, metadata)
            elif product_id.startswith("sub_"):
                return await self._setup_subscription(product_id, customer_email, metadata)
            else:
                raise ValueError(f"Unknown product type: {product_id}")
                
        except Exception as e:
            logger.error(f"Delivery failed: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    async def _deliver_digital_product(self, product_id: str, customer_email: str,
                                     metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Send download links via email."""
        download_url = f"https://download.example.com/{product_id}/{metadata.get('order_id')}"
        
        # Prepare email
        msg = MIMEMultipart()
        msg["From"] = self.from_email
        msg["To"] = customer_email
        msg["Subject"] = metadata.get("subject", "Your Download is Ready!")
        
        body = f"""
        Thank you for your purchase!
        
        Download link: {download_url}
        
        Order ID: {metadata.get('order_id')}
        """
        
        msg.attach(MIMEText(body, "plain"))
        
        # Send email
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_pass)
            server.send_message(msg)
            
        logger.info(f"Sent download link to {customer_email} for product {product_id}")
        return {"status": "success", "download_url": download_url}
        
    async def _setup_subscription(self, product_id: str, customer_email: str,
                                metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Provision subscription access."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.example.com/subscriptions",
                json={
                    "customer_email": customer_email,
                    "product_id": product_id,
                    "metadata": metadata
                }
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"Subscription API error: {await resp.text()}")
                return await resp.json()
