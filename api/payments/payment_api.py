"""
Payment Processing API - Handle payments, subscriptions, and invoices.

Endpoints:
- POST /payments/create - Create a payment
- POST /payments/subscribe - Create a subscription
- GET /payments/invoices - Get invoice history
- POST /payments/webhook - Payment webhook handler
"""

import os
import json
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from core.database import query_db

# Initialize payment gateways
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
})

executor = ThreadPoolExecutor(max_workers=10)

def _make_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(body)
    }

def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create error response."""
    return _make_response(status_code, {"error": message})

async def handle_create_payment(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a payment."""
    try:
        amount = float(body.get('amount', 0))
        currency = body.get('currency', 'usd')
        payment_method = body.get('payment_method', 'stripe')
        description = body.get('description', '')
        metadata = body.get('metadata', {})
        
        def process_payment():
            if payment_method == 'stripe':
                intent = stripe.PaymentIntent.create(
                    amount=int(amount * 100),
                    currency=currency,
                    description=description,
                    metadata=metadata
                )
                return intent
            elif payment_method == 'paypal':
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": str(amount),
                            "currency": currency
                        },
                        "description": description
                    }],
                    "redirect_urls": {
                        "return_url": os.getenv('PAYPAL_RETURN_URL'),
                        "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                    }
                })
                if payment.create():
                    return payment
                raise Exception(payment.error)
            else:
                raise Exception("Unsupported payment method")
        
        # Process payment in background thread
        future = executor.submit(process_payment)
        payment = future.result()
        
        return _make_response(200, {
            "success": True,
            "payment_id": payment.id,
            "status": payment.status,
            "amount": amount,
            "currency": currency
        })
        
    except Exception as e:
        return _error_response(500, f"Payment failed: {str(e)}")

async def handle_create_subscription(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a subscription."""
    try:
        plan_id = body.get('plan_id')
        customer_id = body.get('customer_id')
        payment_method = body.get('payment_method', 'stripe')
        metadata = body.get('metadata', {})
        
        def process_subscription():
            if payment_method == 'stripe':
                subscription = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{"plan": plan_id}],
                    expand=["latest_invoice.payment_intent"],
                    metadata=metadata
                )
                return subscription
            elif payment_method == 'paypal':
                agreement = paypalrestsdk.BillingAgreement({
                    "name": "Subscription Agreement",
                    "description": "Recurring Payment",
                    "start_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                    "plan": {"id": plan_id},
                    "payer": {"payment_method": "paypal"},
                    "shipping_address": metadata.get('shipping_address', {})
                })
                if agreement.create():
                    return agreement
                raise Exception(agreement.error)
            else:
                raise Exception("Unsupported payment method")
        
        future = executor.submit(process_subscription)
        subscription = future.result()
        
        return _make_response(200, {
            "success": True,
            "subscription_id": subscription.id,
            "status": subscription.status
        })
        
    except Exception as e:
        return _error_response(500, f"Subscription failed: {str(e)}")

async def handle_get_invoices(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Get invoice history."""
    try:
        customer_id = query_params.get('customer_id')
        limit = int(query_params.get('limit', 10))
        offset = int(query_params.get('offset', 0))
        
        sql = f"""
        SELECT id, invoice_number, amount, currency, status, created_at, paid_at
        FROM invoices
        WHERE customer_id = '{customer_id}'
        ORDER BY created_at DESC
        LIMIT {limit}
        OFFSET {offset}
        """
        
        result = await query_db(sql)
        invoices = result.get("rows", [])
        
        return _make_response(200, {
            "invoices": invoices,
            "total": len(invoices)
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to get invoices: {str(e)}")

async def handle_payment_webhook(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle payment webhook events."""
    try:
        event_type = body.get('type')
        data = body.get('data', {})
        
        if event_type == 'payment.succeeded':
            # Process successful payment
            payment_id = data.get('id')
            amount = data.get('amount')
            currency = data.get('currency')
            
            # Update database and trigger fulfillment
            await query_db(f"""
                INSERT INTO payments (id, amount, currency, status, created_at)
                VALUES ('{payment_id}', {amount}, '{currency}', 'completed', NOW())
            """)
            
        elif event_type == 'subscription.created':
            # Process new subscription
            subscription_id = data.get('id')
            customer_id = data.get('customer_id')
            plan_id = data.get('plan_id')
            
            await query_db(f"""
                INSERT INTO subscriptions (id, customer_id, plan_id, status, created_at)
                VALUES ('{subscription_id}', '{customer_id}', '{plan_id}', 'active', NOW())
            """)
            
        return _make_response(200, {"success": True})
        
    except Exception as e:
        return _error_response(500, f"Webhook processing failed: {str(e)}")

def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route payment API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # POST /payments/create
    if len(parts) == 2 and parts[0] == "payments" and parts[1] == "create" and method == "POST":
        return handle_create_payment(json.loads(body or "{}"))
    
    # POST /payments/subscribe
    if len(parts) == 2 and parts[0] == "payments" and parts[1] == "subscribe" and method == "POST":
        return handle_create_subscription(json.loads(body or "{}"))
    
    # GET /payments/invoices
    if len(parts) == 2 and parts[0] == "payments" and parts[1] == "invoices" and method == "GET":
        return handle_get_invoices(query_params)
    
    # POST /payments/webhook
    if len(parts) == 2 and parts[0] == "payments" and parts[1] == "webhook" and method == "POST":
        return handle_payment_webhook(json.loads(body or "{}"))
    
    return _error_response(404, "Not found")

__all__ = ["route_request"]
