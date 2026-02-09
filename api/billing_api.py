"""
Billing API - Handle subscriptions, invoices and payments.
"""
import json
from typing import Dict, List, Optional

from core.billing_service import BillingService
from core.database import query_db

def _make_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(body)
    }

def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create error response."""
    return _make_response(status_code, {"error": message})

async def handle_create_subscription(body: Dict) -> Dict:
    """Create a new subscription."""
    try:
        customer_id = body.get("customer_id")
        plan_id = body.get("plan_id")
        
        if not customer_id or not plan_id:
            return _error_response(400, "Missing customer_id or plan_id")
            
        billing = BillingService(query_db)
        result = billing.create_subscription(customer_id, plan_id)
        
        if not result.get("success"):
            return _error_response(400, result.get("error", "Failed to create subscription"))
            
        return _make_response(201, {
            "subscription_id": result["subscription_id"],
            "invoice_id": result["invoice_id"]
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to create subscription: {str(e)}")

async def handle_process_payment(body: Dict) -> Dict:
    """Process payment for an invoice."""
    try:
        invoice_id = body.get("invoice_id")
        payment_method = body.get("payment_method", "card")
        
        if not invoice_id:
            return _error_response(400, "Missing invoice_id")
            
        billing = BillingService(query_db)
        result = billing.process_payment(invoice_id, payment_method)
        
        if not result.get("success"):
            return _error_response(400, result.get("error", "Payment failed"))
            
        return _make_response(200, {"success": True})
        
    except Exception as e:
        return _error_response(500, f"Payment processing failed: {str(e)}")

async def handle_get_invoices(query_params: Dict) -> Dict:
    """Get invoices for a customer or subscription."""
    try:
        customer_id = query_params.get("customer_id")
        subscription_id = query_params.get("subscription_id")
        status = query_params.get("status")
        
        where_clauses = []
        if customer_id:
            where_clauses.append(f"s.customer_id = '{customer_id}'")
        if subscription_id:
            where_clauses.append(f"i.subscription_id = '{subscription_id}'")
        if status:
            where_clauses.append(f"i.status = '{status}'")
            
        where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        sql = f"""
        SELECT 
            i.id, i.subscription_id, i.amount_cents, i.currency,
            i.status, i.due_date, i.paid_at, i.created_at,
            p.name as plan_name, p.billing_cycle_days
        FROM invoices i
        JOIN subscriptions s ON i.subscription_id = s.id
        JOIN billing_plans p ON s.plan_id = p.id
        {where}
        ORDER BY i.created_at DESC
        LIMIT 50
        """
        
        result = await query_db(sql)
        return _make_response(200, {"invoices": result.get("rows", [])})
        
    except Exception as e:
        return _error_response(500, f"Failed to get invoices: {str(e)}")

def route_request(path: str, method: str, query_params: Dict, body: Optional[str] = None) -> Dict:
    """Route billing API requests."""
    if method == "OPTIONS":
        return _make_response(200, {})
        
    try:
        body_data = json.loads(body) if body else {}
    except:
        body_data = {}
        
    parts = [p for p in path.split("/") if p]
    
    # POST /billing/subscriptions
    if len(parts) == 2 and parts[0] == "billing" and parts[1] == "subscriptions" and method == "POST":
        return handle_create_subscription(body_data)
        
    # POST /billing/payments
    if len(parts) == 2 and parts[0] == "billing" and parts[1] == "payments" and method == "POST":
        return handle_process_payment(body_data)
        
    # GET /billing/invoices
    if len(parts) == 2 and parts[0] == "billing" and parts[1] == "invoices" and method == "GET":
        return handle_get_invoices(query_params)
        
    return _error_response(404, "Not found")

__all__ = ["route_request"]
