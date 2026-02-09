"""
Billing API - Handle customer onboarding and subscription management.
"""

import json
from typing import Dict, Optional

from billing.saas_platform import SaaSPlatform
from core.database import query_db

platform = SaaSPlatform()

async def handle_customer_onboard(data: Dict) -> Dict:
    """Handle new customer onboarding."""
    required_fields = ["name", "email", "plan"]
    if not all(field in data for field in required_fields):
        return {
            "success": False,
            "error": "Missing required fields",
            "required": required_fields
        }

    success, result = await platform.onboard_customer(data)
    if not success:
        return {"success": False, "error": result}

    return {
        "success": True,
        "client_secret": result,
        "customer_email": data["email"]
    }

async def handle_webhook(event: Dict) -> Dict:
    """Process Stripe webhook events."""
    success = await platform.process_webhook(event)
    return {"success": success}

async def handle_customer_status(customer_id: str) -> Dict:
    """Get customer status and details."""
    customer = await platform.get_customer_status(customer_id)
    if not customer:
        return {"success": False, "error": "Customer not found"}
    
    return {"success": True, "customer": customer}

def route_request(path: str, method: str, body: Optional[str] = None) -> Dict:
    """Route billing API requests."""
    try:
        data = json.loads(body) if body else {}
        
        if path == "/billing/onboard" and method == "POST":
            return handle_customer_onboard(data)
        elif path == "/billing/webhook" and method == "POST":
            return handle_webhook(data)
        elif path.startswith("/billing/customer/") and method == "GET":
            customer_id = path.split("/")[-1]
            return handle_customer_status(customer_id)
            
        return {"success": False, "error": "Not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}
