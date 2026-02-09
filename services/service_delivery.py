from typing import Dict, Optional
from core.database import query_db
import json
from datetime import datetime, timezone

class ServiceDelivery:
    async def fulfill_order(self, product_id: str, customer_id: str, metadata: Dict) -> Dict:
        """Automatically fulfill a digital service/product."""
        try:
            # Get product details
            product = await query_db(
                f"SELECT * FROM products WHERE id = '{product_id}'"
            )
            if not product.get("rows"):
                return {"success": False, "error": "Product not found"}

            product_data = product["rows"][0]
            
            # Create fulfillment record
            result = await query_db(
                f"""
                INSERT INTO service_fulfillments (
                    id, product_id, customer_id, status,
                    metadata, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{product_id}',
                    '{customer_id}',
                    'pending',
                    '{json.dumps(metadata)}',
                    NOW(),
                    NOW()
                )
                RETURNING id
                """
            )
            
            fulfillment_id = result["rows"][0]["id"]
            
            # Trigger automated delivery (e.g. send email, generate download link, etc)
            # This would be customized based on your product type
            delivery_result = await self._deliver_product(product_data, customer_id, fulfillment_id)
            
            if not delivery_result.get("success"):
                return delivery_result

            # Update fulfillment status
            await query_db(
                f"""
                UPDATE service_fulfillments
                SET status = 'completed',
                    updated_at = NOW()
                WHERE id = '{fulfillment_id}'
                """
            )
            
            return {"success": True, "fulfillment_id": fulfillment_id}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _deliver_product(self, product: Dict, customer_id: str, fulfillment_id: str) -> Dict:
        """Product-specific delivery logic."""
        # Example: For digital products, generate download link
        if product["product_type"] == "digital":
            download_url = f"https://download.example.com/{fulfillment_id}"
            return {
                "success": True,
                "download_url": download_url,
                "message": "Product delivered via download link"
            }
        
        # Add other product type handlers as needed
        return {"success": False, "error": "Unsupported product type"}
