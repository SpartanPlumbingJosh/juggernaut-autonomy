"""
Customer API - Handle customer onboarding and management.

Endpoints:
- POST /customers - Create new customer
- GET /customers/{id} - Get customer details
- PUT /customers/{id} - Update customer
"""

import json
from typing import Any, Dict, Optional

from core.database import query_db


def _make_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(body)
    }


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create error response."""
    return _make_response(status_code, {"error": message})


async def create_customer(customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new customer record."""
    try:
        required_fields = ["email", "name"]
        for field in required_fields:
            if not customer_data.get(field):
                return _error_response(400, f"Missing required field: {field}")

        sql = f"""
        INSERT INTO customers (
            id, email, name, metadata, created_at, updated_at
        ) VALUES (
            gen_random_uuid(),
            '{customer_data["email"]}',
            '{customer_data["name"]}',
            '{json.dumps(customer_data.get("metadata", {}))}'::jsonb,
            NOW(),
            NOW()
        )
        RETURNING id
        """
        
        result = await query_db(sql)
        customer_id = result.get("rows", [{}])[0].get("id")
        
        return _make_response(201, {
            "customer_id": customer_id,
            "status": "created"
        })
        
    except Exception as e:
        return _error_response(500, f"Customer creation failed: {str(e)}")


async def get_customer(customer_id: str) -> Dict[str, Any]:
    """Get customer details."""
    try:
        sql = f"""
        SELECT id, email, name, metadata, created_at, updated_at
        FROM customers
        WHERE id = '{customer_id}'
        """
        
        result = await query_db(sql)
        customer = result.get("rows", [{}])[0]
        
        if not customer.get("id"):
            return _error_response(404, "Customer not found")
            
        return _make_response(200, customer)
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch customer: {str(e)}")


async def update_customer(customer_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update customer record."""
    try:
        if not update_data:
            return _error_response(400, "No update data provided")

        updates = []
        if "email" in update_data:
            updates.append(f"email = '{update_data['email']}'")
        if "name" in update_data:
            updates.append(f"name = '{update_data['name']}'")
        if "metadata" in update_data:
            updates.append(f"metadata = '{json.dumps(update_data['metadata'])}'::jsonb")
            
        if not updates:
            return _error_response(400, "No valid fields to update")

        sql = f"""
        UPDATE customers
        SET {", ".join(updates)}, updated_at = NOW()
        WHERE id = '{customer_id}'
        RETURNING id
        """
        
        result = await query_db(sql)
        if not result.get("rows"):
            return _error_response(404, "Customer not found")
            
        return _make_response(200, {
            "customer_id": customer_id,
            "status": "updated"
        })
        
    except Exception as e:
        return _error_response(500, f"Customer update failed: {str(e)}")


def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route customer API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # POST /customers
    if len(parts) == 1 and parts[0] == "customers" and method == "POST":
        try:
            customer_data = json.loads(body or "{}")
            return create_customer(customer_data)
        except json.JSONDecodeError:
            return _error_response(400, "Invalid JSON payload")
    
    # GET /customers/{id}
    if len(parts) == 2 and parts[0] == "customers" and method == "GET":
        return get_customer(parts[1])
    
    # PUT /customers/{id}
    if len(parts) == 2 and parts[0] == "customers" and method == "PUT":
        try:
            update_data = json.loads(body or "{}")
            return update_customer(parts[1], update_data)
        except json.JSONDecodeError:
            return _error_response(400, "Invalid JSON payload")
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
