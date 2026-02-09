"""
Digital Storefront API - Handle product listings, purchases and deliveries.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import query_db
from api.revenue_api import _make_response, _error_response


async def handle_product_list() -> Dict[str, Any]:
    """Get available products."""
    try:
        sql = """
        SELECT id, name, description, price_cents, digital_delivery_url, 
               created_at, updated_at, metadata
        FROM products
        WHERE status = 'active'
        ORDER BY created_at DESC
        """
        result = await query_db(sql)
        products = result.get("rows", [])
        return _make_response(200, {"products": products})
    except Exception as e:
        return _error_response(500, f"Failed to fetch products: {str(e)}")


async def handle_purchase(body: Dict[str, Any]) -> Dict[str, Any]:
    """Process a product purchase."""
    try:
        product_id = body.get("product_id")
        email = body.get("email")
        payment_token = body.get("payment_token")
        
        if not product_id or not email or not payment_token:
            return _error_response(400, "Missing required fields")
            
        # Get product details
        product_sql = f"""
        SELECT id, price_cents, digital_delivery_url
        FROM products
        WHERE id = '{product_id}' AND status = 'active'
        """
        product_result = await query_db(product_sql)
        product = product_result.get("rows", [{}])[0]
        
        if not product:
            return _error_response(404, "Product not found")
            
        # Process payment (stub - integrate with payment gateway)
        payment_success = True  # Replace with actual payment processing
        
        if not payment_success:
            return _error_response(402, "Payment failed")
            
        # Record transaction
        transaction_id = str(uuid.uuid4())
        transaction_sql = f"""
        INSERT INTO transactions (
            id, product_id, email, amount_cents, status,
            created_at, updated_at, metadata
        ) VALUES (
            '{transaction_id}',
            '{product_id}',
            '{email}',
            {product['price_cents']},
            'completed',
            NOW(),
            NOW(),
            '{{"payment_token": "{payment_token}"}}'::jsonb
        )
        """
        await query_db(transaction_sql)
        
        # Record revenue event
        revenue_sql = f"""
        INSERT INTO revenue_events (
            id, event_type, amount_cents, currency,
            source, metadata, recorded_at, created_at
        ) VALUES (
            gen_random_uuid(),
            'revenue',
            {product['price_cents']},
            'USD',
            'storefront',
            '{{"product_id": "{product_id}", "transaction_id": "{transaction_id}"}}'::jsonb,
            NOW(),
            NOW()
        )
        """
        await query_db(revenue_sql)
        
        return _make_response(200, {
            "success": True,
            "transaction_id": transaction_id,
            "delivery_url": product['digital_delivery_url']
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to process purchase: {str(e)}")


def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route storefront API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # GET /storefront/products
    if len(parts) == 2 and parts[0] == "storefront" and parts[1] == "products" and method == "GET":
        return handle_product_list()
    
    # POST /storefront/purchase
    if len(parts) == 2 and parts[0] == "storefront" and parts[1] == "purchase" and method == "POST":
        try:
            body_data = json.loads(body) if body else {}
            return handle_purchase(body_data)
        except Exception as e:
            return _error_response(400, f"Invalid request body: {str(e)}")
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
