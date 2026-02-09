import os
import json
from typing import Dict, Any
from core.database import query_db

async def deliver_product(transaction_id: str, product_id: str, customer_email: str) -> Dict[str, Any]:
    """Deliver digital product to customer."""
    try:
        # Get product details
        product = await query_db(f"""
            SELECT * FROM products WHERE id = '{product_id}'
        """)
        if not product.get("rows"):
            return {"success": False, "error": "Product not found"}
        
        product_data = product.get("rows")[0]
        
        # Generate delivery content
        delivery_content = {
            "product_id": product_id,
            "product_name": product_data.get("name"),
            "download_url": product_data.get("download_url"),
            "license_key": generate_license_key(),
            "customer_email": customer_email
        }
        
        # Record delivery
        await query_db(f"""
            INSERT INTO product_deliveries (
                id, transaction_id, product_id, delivery_data, created_at
            ) VALUES (
                gen_random_uuid(),
                '{transaction_id}',
                '{product_id}',
                '{json.dumps(delivery_content)}'::jsonb,
                NOW()
            )
        """)
        
        # Send email with download instructions
        await send_delivery_email(customer_email, delivery_content)
        
        return {"success": True, "delivery": delivery_content}
    
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_license_key() -> str:
    """Generate a unique license key."""
    import uuid
    return str(uuid.uuid4()).replace("-", "")[:16].upper()

async def send_delivery_email(email: str, content: Dict[str, Any]) -> bool:
    """Send product delivery email."""
    # Implement email sending logic here
    return True
