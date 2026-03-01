"""
Product/service delivery mechanisms for revenue automation.
Handles both digital and physical product fulfillment.
"""
import logging
from typing import Dict, Any
import boto3
from email.mime.text import MIMEText
import smtplib

logger = logging.getLogger(__name__)

class ProductDelivery:
    def __init__(self, config: Dict[str, Any]):
        # AWS S3 for digital downloads
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=config.get("aws_access_key"),
            aws_secret_access_key=config.get("aws_secret_key"),
            region_name=config.get("aws_region", "us-east-1")
        )
        
        # Email configuration
        self.smtp_config = config.get("smtp", {})
        
    async def deliver_product(self,
                            order_details: Dict[str, Any],
                            customer_details: Dict[str, Any],
                            product_type: str) -> Dict[str, Any]:
        """
        Handle product delivery based on product type.
        Returns delivery status and tracking/access info.
        """
        try:
            if product_type == "digital":
                return await self._deliver_digital_product(order_details, customer_details)
            elif product_type == "service":
                return await self._deliver_service(order_details, customer_details)
            elif product_type == "physical":
                return await self._initiate_physical_shipment(order_details, customer_details)
            else:
                raise ValueError(f"Unknown product type: {product_type}")
                
        except Exception as e:
            logger.error(f"Product delivery failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }

    async def _deliver_digital_product(self,
                                    order_details: Dict[str, Any],
                                    customer_details: Dict[str, Any]) -> Dict[str, Any]:
        """Generate and send download links for digital products"""
        try:
            bucket = order_details["s3_bucket"]
            key = order_details["s3_key"]
            filename = order_details.get("filename", "download.zip")
            
            # Generate pre-signed URL
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=3600 * 24 * 7  # 1 week expiry
            )
            
            # Send download email
            subject = f"Your download: {order_details.get('product_name', 'Product')}"
            body = f"""Here's your download link:\n\n{url}\n\n
                       Link will expire in 7 days."""
            
            await self._send_email(
                to_email=customer_details["email"],
                subject=subject,
                body=body
            )
            
            return {
                "status": "delivered",
                "delivery_method": "email",
                "download_url": url,
                "expires_in": "7 days"
            }
            
        except Exception as e:
            raise Exception(f"Digital delivery failed: {str(e)}")

    async def _deliver_service(self,
                             order_details: Dict[str, Any],
                             customer_details: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule service delivery via calendar invite"""
        try:
            # In a real implementation, we'd integrate with calendar APIs
            # For MVP, we'll just email booking details
            subject = f"Your {order_details.get('service_name', 'Service')} booking"
            body = f"""Thank you for your booking!\n\n
                       Booking details: {order_details.get('details', 'Contact us')}"""
            
            await self._send_email(
                to_email=customer_details["email"],
                subject=subject,
                body=body
            )
            
            return {
                "status": "scheduled",
                "delivery_method": "email",
                "next_steps": "We'll contact you shortly"
            }
            
        except Exception as e:
            raise Exception(f"Service delivery scheduling failed: {str(e)}")

    async def _initiate_physical_shipment(self,
                                        order_details: Dict[str, Any],
                                        customer_details: Dict[str, Any]) -> Dict[str, Any]:
        """Initiate physical shipment via logistics provider"""
        # In MVP, we'll just generate a tracking number
        # In production, integrate with shipping API
        tracking_number = f"TRK{hash(str(order_details)+str(customer_details))}"
        
        return {
            "status": "processing",
            "tracking_number": tracking_number,
            "estimated_delivery": "5-7 business days",
            "shipping_method": "standard"
        }

    async def _send_email(self,
                        to_email: str,
                        subject: str,
                        body: str) -> None:
        """Internal email sending utility"""
        if not self.smtp_config:
            logger.warning("SMTP not configured - skipping email send")
            return
            
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = self.smtp_config["from_email"]
        msg['To'] = to_email
        
        try:
            with smtplib.SMTP(self.smtp_config["host"], self.smtp_config["port"]) as server:
                if self.smtp_config.get("use_tls"):
                    server.starttls()
                if self.smtp_config.get("username"):
                    server.login(
                        self.smtp_config["username"],
                        self.smtp_config["password"]
                    )
                server.send_message(msg)
        except Exception as e:
            raise Exception(f"Email sending failed: {str(e)}")
