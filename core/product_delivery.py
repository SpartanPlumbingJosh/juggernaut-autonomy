import logging
from typing import Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

async def deliver_product(product_id: str, customer_email: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Automatically deliver product/service to customer"""
    try:
        # Here you would implement your product delivery logic
        # This could include:
        # - Generating/downloading digital products
        # - Triggering service provisioning
        # - Sending access credentials
        # - Adding to mailing lists
        # - Etc.
        
        # Example: Send welcome email with access details
        await _send_welcome_email(customer_email, product_id)
        
        # Example: Log delivery
        await _log_delivery(product_id, customer_email)
        
        return {"success": True, "message": "Product delivered successfully"}
        
    except Exception as e:
        logger.error(f"Failed to deliver product: {str(e)}")
        return {"success": False, "error": str(e)}

async def _send_welcome_email(email: str, product_id: str) -> Dict[str, Any]:
    """Send welcome email with product access details"""
    try:
        # Implement your email sending logic here
        # Using SMTP, SendGrid, Mailgun, etc.
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")
        return {"success": False, "error": str(e)}

async def _log_delivery(product_id: str, customer_email: str) -> Dict[str, Any]:
    """Log product delivery to database"""
    try:
        from core.database import query_db
        
        sql = f"""
        INSERT INTO product_deliveries (
            id, product_id, customer_email, delivered_at, created_at
        ) VALUES (
            gen_random_uuid(),
            '{product_id}',
            '{customer_email}',
            NOW(),
            NOW()
        )
        """
        await query_db(sql)
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to log delivery: {str(e)}")
        return {"success": False, "error": str(e)}
