import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db

async def create_customer_account(customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create new customer account."""
    try:
        sql = f"""
        INSERT INTO customers (
            id, email, name, metadata, created_at, updated_at
        ) VALUES (
            gen_random_uuid(),
            '{customer_data.get("email", "").replace("'", "''")}',
            '{customer_data.get("name", "").replace("'", "''")}',
            '{json.dumps(customer_data.get("metadata", {}))}'::jsonb,
            NOW(),
            NOW()
        )
        RETURNING id
        """
        
        result = await query_db(sql)
        customer_id = result.get("rows", [{}])[0].get("id", "")
        
        return {"success": True, "customer_id": customer_id}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def deliver_service(customer_id: str, service_id: str, payment_id: str) -> Dict[str, Any]:
    """Deliver purchased service to customer."""
    try:
        # Get service details
        service_sql = f"""
        SELECT id, name, delivery_method, delivery_data 
        FROM services 
        WHERE id = '{service_id}'
        """
        service_result = await query_db(service_sql)
        service = service_result.get("rows", [{}])[0]
        
        if not service:
            return {"success": False, "error": "Service not found"}
            
        # Record service delivery
        delivery_sql = f"""
        INSERT INTO service_deliveries (
            id, customer_id, service_id, payment_id, status, delivered_at, created_at
        ) VALUES (
            gen_random_uuid(),
            '{customer_id}',
            '{service_id}',
            '{payment_id}',
            'pending',
            NOW(),
            NOW()
        )
        RETURNING id
        """
        delivery_result = await query_db(delivery_sql)
        delivery_id = delivery_result.get("rows", [{}])[0].get("id", "")
        
        # Trigger actual delivery based on service type
        delivery_method = service.get("delivery_method", "")
        delivery_data = service.get("delivery_data", {})
        
        if delivery_method == "email":
            # Send email with access details
            pass
        elif delivery_method == "api":
            # Call external API to provision service
            pass
        elif delivery_method == "download":
            # Generate download link
            pass
            
        # Mark delivery as complete
        await query_db(f"""
            UPDATE service_deliveries 
            SET status = 'completed',
                updated_at = NOW()
            WHERE id = '{delivery_id}'
        """)
        
        return {"success": True, "delivery_id": delivery_id}
    except Exception as e:
        return {"success": False, "error": str(e)}
