"""
Payment API - Handle payment processing, subscriptions, and billing.

Endpoints:
- POST /payment/create - Create payment intent
- POST /payment/subscribe - Create subscription
- POST /payment/webhook - Payment webhook handler
- GET /payment/invoices - Get invoices
"""

import json
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import query_db

# Initialize payment gateways
stripe.api_key = "sk_test_..."  # TODO: Move to config
paypalrestsdk.configure({
    "mode": "sandbox",  # TODO: Move to config
    "client_id": "...",
    "client_secret": "..."
})

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
    """Create a payment intent."""
    try:
        amount_cents = int(float(body.get("amount")) * 100)
        currency = body.get("currency", "usd")
        description = body.get("description", "")
        metadata = body.get("metadata", {})
        
        # Create Stripe payment intent
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            description=description,
            metadata=metadata
        )
        
        return _make_response(200, {
            "client_secret": intent.client_secret,
            "payment_id": intent.id,
            "amount_cents": amount_cents,
            "currency": currency
        })
        
    except Exception as e:
        return _error_response(500, f"Payment creation failed: {str(e)}")

async def handle_create_subscription(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a subscription."""
    try:
        plan_id = body.get("plan_id")
        customer_email = body.get("email")
        payment_method = body.get("payment_method")
        
        # Create Stripe customer
        customer = stripe.Customer.create(
            email=customer_email,
            payment_method=payment_method,
            invoice_settings={
                'default_payment_method': payment_method
            }
        )
        
        # Create subscription
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"plan": plan_id}],
            expand=["latest_invoice.payment_intent"]
        )
        
        return _make_response(200, {
            "subscription_id": subscription.id,
            "status": subscription.status,
            "customer_id": customer.id,
            "latest_invoice": subscription.latest_invoice.id
        })
        
    except Exception as e:
        return _error_response(500, f"Subscription creation failed: {str(e)}")

async def handle_payment_webhook(body: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
    """Handle payment webhooks."""
    try:
        event = None
        payload = json.dumps(body)
        sig_header = headers.get("Stripe-Signature")
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, stripe.api_key
            )
        except ValueError as e:
            return _error_response(400, "Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            return _error_response(400, "Invalid signature")
            
        # Handle events
        if event.type == "payment_intent.succeeded":
            payment_intent = event.data.object
            await record_payment(payment_intent)
            
        elif event.type == "invoice.payment_succeeded":
            invoice = event.data.object
            await record_invoice(invoice)
            
        elif event.type == "charge.refunded":
            charge = event.data.object
            await record_refund(charge)
            
        return _make_response(200, {"status": "success"})
        
    except Exception as e:
        return _error_response(500, f"Webhook processing failed: {str(e)}")

async def record_payment(payment_intent: Any) -> None:
    """Record successful payment."""
    amount_cents = payment_intent.amount
    currency = payment_intent.currency
    payment_id = payment_intent.id
    metadata = payment_intent.metadata
    
    await query_db(f"""
        INSERT INTO revenue_events (
            id, event_type, amount_cents, currency,
            source, metadata, recorded_at, created_at
        ) VALUES (
            gen_random_uuid(),
            'revenue',
            {amount_cents},
            '{currency}',
            'stripe',
            '{json.dumps(metadata)}'::jsonb,
            NOW(),
            NOW()
        )
    """)
    
    # Update current_cents balance
    await query_db(f"""
        UPDATE revenue_accounts
        SET current_cents = current_cents + {amount_cents}
        WHERE currency = '{currency}'
    """)

async def record_invoice(invoice: Any) -> None:
    """Record invoice payment."""
    amount_cents = invoice.amount_paid
    currency = invoice.currency
    invoice_id = invoice.id
    subscription_id = invoice.subscription
    
    await query_db(f"""
        INSERT INTO revenue_events (
            id, event_type, amount_cents, currency,
            source, metadata, recorded_at, created_at
        ) VALUES (
            gen_random_uuid(),
            'revenue',
            {amount_cents},
            '{currency}',
            'stripe',
            '{{"invoice_id": "{invoice_id}", "subscription_id": "{subscription_id}"}}'::jsonb,
            NOW(),
            NOW()
        )
    """)
    
    # Update current_cents balance
    await query_db(f"""
        UPDATE revenue_accounts
        SET current_cents = current_cents + {amount_cents}
        WHERE currency = '{currency}'
    """)

async def record_refund(charge: Any) -> None:
    """Record refund."""
    amount_cents = charge.amount_refunded
    currency = charge.currency
    payment_id = charge.payment_intent
    
    await query_db(f"""
        INSERT INTO revenue_events (
            id, event_type, amount_cents, currency,
            source, metadata, recorded_at, created_at
        ) VALUES (
            gen_random_uuid(),
            'refund',
            {amount_cents},
            '{currency}',
            'stripe',
            '{{"payment_id": "{payment_id}"}}'::jsonb,
            NOW(),
            NOW()
        )
    """)
    
    # Update current_cents balance
    await query_db(f"""
        UPDATE revenue_accounts
        SET current_cents = current_cents - {amount_cents}
        WHERE currency = '{currency}'
    """)

async def handle_get_invoices(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Get invoices with pagination."""
    try:
        limit = int(query_params.get("limit", 50))
        offset = int(query_params.get("offset", 0))
        
        invoices = stripe.Invoice.list(
            limit=limit,
            offset=offset,
            expand=["data.customer", "data.subscription"]
        )
        
        return _make_response(200, {
            "invoices": invoices.data,
            "total": invoices.total_count,
            "limit": limit,
            "offset": offset
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch invoices: {str(e)}")

def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route payment API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # POST /payment/create
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "create" and method == "POST":
        return handle_create_payment(json.loads(body or "{}"))
    
    # POST /payment/subscribe
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "subscribe" and method == "POST":
        return handle_create_subscription(json.loads(body or "{}"))
    
    # POST /payment/webhook
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "webhook" and method == "POST":
        return handle_payment_webhook(json.loads(body or "{}"), query_params)
    
    # GET /payment/invoices
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "invoices" and method == "GET":
        return handle_get_invoices(query_params)
    
    return _error_response(404, "Not found")

__all__ = ["route_request"]
