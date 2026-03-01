"""
Digital Product Storefront API and fulfillment automation.

Features:
- Product listings
- Payment webhook processing
- Automated delivery
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

from core.database import query_db

logger = logging.getLogger(__name__)

# Configuration - would normally be in environment vars/config
DIGITAL_PRODUCTS = [
    {
        "id": "prod_basic",
        "name": "Basic Digital Product",
        "description": "Entry-level digital download",
        "price_cents": 990,
        "delivery_url": "https://cdn.example.com/products/basic.zip",
        "download_limit": 3
    },
    {
        "id": "prod_premium", 
        "name": "Premium Bundle",
        "description": "Complete digital package",
        "price_cents": 2490,
        "delivery_url": "https://cdn.example.com/products/premium.zip",
        "download_limit": 5
    }
]

async def handle_product_listings() -> Dict[str, Any]:
    """Get available digital products."""
    try:
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "products": DIGITAL_PRODUCTS,
                "timestamp": datetime.utcnow().isoformat()
            })
        }
    except Exception as e:
        logger.error(f"Failed to fetch products: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to fetch products"})
        }

async def handle_payment_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process payment webhook and trigger fulfillment."""
    try:
        payment_data = event.get("data", {})
        product_id = payment_data.get("product_id")
        customer_email = payment_data.get("customer_email")
        payment_id = payment_data.get("payment_id")
        
        # Validate product exists
        product = next((p for p in DIGITAL_PRODUCTS if p["id"] == product_id), None)
        if not product:
            logger.error(f"Invalid product ID in payment: {product_id}")
            return {"statusCode": 400, "body": "Invalid product"}
        
        # Create fulfillment record
        fulfillment_id = str(uuid.uuid4())
        delivery_url = product["delivery_url"]
        
        await query_db(f"""
            INSERT INTO orders (
                id, 
                product_id,
                payment_id,
                customer_email,
                price_cents,
                fulfillment_status,
                download_url,
                downloads_remaining,
                created_at
            ) VALUES (
                '{fulfillment_id}',
                '{product_id}',
                '{payment_id}',
                '{customer_email.replace("'", "''")}',
                {product["price_cents"]},
                'pending',
                '{delivery_url}',
                {product["download_limit"]},
                NOW()
            )
        """)
        
        # Send download instructions (in real system this would be email/SQS/etc)
        logger.info(f"Created order {fulfillment_id} for payment {payment_id}")
        
        return {"statusCode": 200, "body": "Payment processed"}
        
    except Exception as e:
        logger.error(f"Payment webhook failed: {str(e)}")
        return {"statusCode": 500, "body": "Payment processing failed"}

async def handle_download_request(order_id: str, email: str) -> Dict[str, Any]:
    """Validate and fulfill download request."""
    try:
        result = await query_db(f"""
            SELECT 
                download_url,
                downloads_remaining,
                fulfillment_status
            FROM orders
            WHERE id = '{order_id}'
            AND customer_email = '{email.replace("'", "''")}'
        """)
        
        order = result.get("rows", [{}])[0] or {}
        
        if not order.get("download_url"):
            return {"statusCode": 404, "body": "Order not found"}
            
        if order.get("fulfillment_status") != "pending":
            return {"statusCode": 403, "body": "Download expired"}
            
        remaining = int(order.get("downloads_remaining", 0))
        if remaining <= 0:
            return {"statusCode": 403, "body": "No downloads remaining"}
            
        # Update download count
        await query_db(f"""
            UPDATE orders SET
                downloads_remaining = {remaining - 1},
                updated_at = NOW()
            WHERE id = '{order_id}'
        """)
        
        return {
            "statusCode": 302,
            "headers": {"Location": order["download_url"]}
        }
        
    except Exception as e:
        logger.error(f"Download failed for order {order_id}: {str(e)}")
        return {"statusCode": 500, "body": "Download failed"}

def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route storefront API requests."""
    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        }
        
    parts = [p for p in path.split("/") if p]
    
    # GET /storefront/products
    if len(parts) == 2 and parts[0] == "storefront" and parts[1] == "products":
        return handle_product_listings()
        
    # POST /storefront/webhook/payment
    if len(parts) == 3 and parts[0] == "storefront" and parts[1] == "webhook" and parts[2] == "payment":
        body_data = json.loads(body) if body else {}
        return handle_payment_webhook(body_data)
        
    # GET /storefront/download/{order_id}?email={email}
    if len(parts) == 3 and parts[0] == "storefront" and parts[1] == "download":
        order_id = parts[2]
        email = query_params.get("email", "")
        return handle_download_request(order_id, email)
        
    return {
        "statusCode": 404,
        "body": "Not found"
    }

__all__ = ["route_request"]
