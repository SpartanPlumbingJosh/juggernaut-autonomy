import json
from typing import Dict, Any
from datetime import datetime
from core.database import query_db

async def deliver_service(payment_data: Dict[str, Any]) -> Dict[str, Any]:
    """Deliver service after successful payment."""
    service_id = payment_data.get("metadata", {}).get("service_id")
    customer_email = payment_data.get("customer_email")
    
    if not service_id or not customer_email:
        return {"success": False, "error": "Missing service or customer data"}
    
    # Record service delivery
    await query_db(f"""
        INSERT INTO service_deliveries (
            id, service_id, customer_email, delivered_at, created_at
        ) VALUES (
            gen_random_uuid(), '{service_id}', '{customer_email}',
            NOW(), NOW()
        )
    """)
    
    # TODO: Implement actual service delivery logic
    # For MVP, we'll just send a confirmation email
    await query_db(f"""
        INSERT INTO email_queue (
            id, recipient, subject, body, created_at
        ) VALUES (
            gen_random_uuid(), '{customer_email}', 'Service Confirmation',
            'Your service has been delivered!', NOW()
        )
    """)
    
    return {"success": True, "message": "Service delivered"}

__all__ = ["deliver_service"]
