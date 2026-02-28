import json
from datetime import datetime
from typing import Dict, Optional

class ServiceDelivery:
    """Handles automated service delivery"""
    
    async def deliver_service(self, user_id: str, product_id: str, payment_intent_id: str) -> Dict:
        """Deliver service to user"""
        try:
            # Get product details
            product = await query_db(f"""
                SELECT * FROM products WHERE id = '{product_id}'
            """)
            product = product.get("rows", [{}])[0]
            
            if not product:
                return {"success": False, "error": "Product not found"}
            
            # Record service delivery
            await query_db(f"""
                INSERT INTO service_deliveries (
                    id, user_id, product_id, payment_intent_id,
                    delivered_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{user_id}',
                    '{product_id}',
                    '{payment_intent_id}',
                    NOW(),
                    NOW()
                )
            """)
            
            # Return service details
            return {
                "success": True,
                "product": product,
                "delivered_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
