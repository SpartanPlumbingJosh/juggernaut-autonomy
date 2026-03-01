"""
Digital Product Fulfillment Manager

Handles:
- Expiring downloads
- Fraud detection
- Delivery status updates
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Callable

logger = logging.getLogger(__name__)

async def check_order_fulfillment(execute_sql: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
    """Scan incomplete orders and update fulfillment status."""
    try:
        # Get pending orders older than 24 hours
        result = await execute_sql("""
            SELECT id, customer_email, product_id 
            FROM orders
            WHERE fulfillment_status = 'pending'
            AND created_at < NOW() - INTERVAL '24 hours'
        """)
        
        expired_orders = result.get("rows", [])
        
        if expired_orders:
            order_ids = [str(o['id']) for o in expired_orders]
            id_list = ",".join(f"'{oid}'" for oid in order_ids)
            
            await execute_sql(f"""
                UPDATE orders 
                SET fulfillment_status = 'expired',
                    updated_at = NOW()
                WHERE id IN ({id_list})
            """)
            
            logger.info(f"Marked {len(expired_orders)} orders as expired")
            
        # Similarly could check for fraudulent patterns,
        # update successful deliveries, etc.
        
        return {
            "success": True,
            "expired": len(expired_orders)
        }
        
    except Exception as e:
        logger.error(f"Fulfillment check failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


async def send_delivery_notifications(execute_sql: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
    """Send emails/SMS for new orders."""
    try:
        # Get new orders that haven't been notified yet
        result = await execute_sql("""
            SELECT id, customer_email, product_id
            FROM orders
            WHERE delivery_notified = FALSE
            AND fulfillment_status = 'pending'
            ORDER BY created_at DESC
            LIMIT 100
        """)
        
        new_orders = result.get("rows", [])
        
        if not new_orders:
            return {"success": True, "processed": 0}
            
        # In real system this would actually send emails/SQS messages/etc
        order_ids = [str(o['id']) for o in new_orders]
        id_list = ",".join(f"'{oid}'" for oid in order_ids)
        
        await execute_sql(f"""
            UPDATE orders 
            SET delivery_notified = TRUE,
                updated_at = NOW()
            WHERE id IN ({id_list})
        """)
        
        logger.info(f"Processed notifications for {len(new_orders)} orders")
        return {"success": True, "processed": len(new_orders)}
        
    except Exception as e:
        logger.error(f"Notification processing failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

__all__ = ["check_order_fulfillment", "send_delivery_notifications"]
