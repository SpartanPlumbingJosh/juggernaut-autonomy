from datetime import datetime
from typing import Dict, Optional
import logging
import boto3
from botocore.exceptions import ClientError

class ProductDelivery:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.getenv('PRODUCT_BUCKET_NAME')

    async def deliver_product(self, product_id: str, customer_email: str) -> Dict:
        """Deliver digital product to customer"""
        try:
            # Generate secure download link
            download_url = self._generate_download_link(product_id)
            
            # Send email with download instructions
            self._send_delivery_email(customer_email, download_url)
            
            return {
                "success": True,
                "download_url": download_url,
                "email_sent": True
            }
        except Exception as e:
            logging.error(f"Product delivery failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _generate_download_link(self, product_id: str) -> str:
        """Generate secure S3 download link"""
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': f"products/{product_id}.zip"
                },
                ExpiresIn=3600  # 1 hour expiration
            )
            return response
        except ClientError as e:
            logging.error(f"S3 link generation failed: {str(e)}")
            raise

    def _send_delivery_email(self, email: str, download_url: str) -> bool:
        """Send product delivery email"""
        # Implement email sending logic
        return True
