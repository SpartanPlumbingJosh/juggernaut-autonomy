"""
Payment Processing API - Handle payments, subscriptions, invoices and webhooks.

Endpoints:
- POST /payment/create - Create payment intent
- POST /payment/subscribe - Create subscription
- POST /payment/webhook - Handle payment webhooks
- GET /payment/invoices - Get invoice history
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
    """Create payment intent."""
    try:
        amount = int(float(body.get("amount", 0)) * 100)
        currency = body.get("currency", "usd")
        description = body.get("description", "")
        metadata = body.get("metadata", {})
        
        # Create Stripe payment intent
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            description=description,
            metadata=metadata
        )
        
        return _make_response(200, {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
            "amount": amount,
            "currency": currency
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to create payment: {str(e)}")

async def handle_create_subscription(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create subscription."""
    try:
        plan_id = body.get("plan_id")
        customer_email = body.get("customer_email")
        payment_method_id = body.get("payment_method_id")
        
        # Create Stripe customer
        customer = stripe.Customer.create(
            email=customer_email,
            payment_method=payment_method_id,
            invoice_settings={
                'default_payment_method': payment_method_id
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
            "client_secret": subscription.latest_invoice.payment_intent.client_secret
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to create subscription: {str(e)}")

async def handle_payment_webhook(body: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
    """Handle payment webhooks."""
    try:
        event = None
        payload = body.get("payload", {})
        
        # Verify Stripe webhook
        sig_header = headers.get("stripe-signature")
        endpoint_secret = "whsec_..."  # TODO: Move to config
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError as e:
            return _error_response(400, f"Invalid payload: {str(e)}")
        except stripe.error.SignatureVerificationError as e:
            return _error_response(400, f"Invalid signature: {str(e)}")
        
        # Handle event types
        if event.type == "payment_intent.succeeded":
            payment_intent = event.data.object
            await handle_successful_payment(payment_intent)
        elif event.type == "payment_intent.payment_failed":
            payment_intent = event.data.object
            await handle_failed_payment(payment_intent)
        elif event.type == "invoice.payment_failed":
            invoice = event.data.object
            await handle_failed_invoice(invoice)
        
        return _make_response(200, {"status": "success"})
        
    except Exception as e:
        return _error_response(500, f"Failed to process webhook: {str(e)}")

async def handle_successful_payment(payment_intent: Any) -> None:
    """Handle successful payment."""
    try:
        await query_db(f"""
            INSERT INTO payments (
                id, amount, currency, status,
                payment_method, customer_email,
                created_at, updated_at
            ) VALUES (
                '{payment_intent.id}',
                {payment_intent.amount},
                '{payment_intent.currency}',
                'succeeded',
                '{payment_intent.payment_method}',
                '{payment_intent.receipt_email}',
                NOW(),
                NOW()
            )
        """)
    except Exception as e:
        raise Exception(f"Failed to record payment: {str(e)}")

async def handle_failed_payment(payment_intent: Any) -> None:
    """Handle failed payment."""
    try:
        await query_db(f"""
            INSERT INTO payments (
                id, amount, currency, status,
                payment_method, customer_email,
                created_at, updated_at
            ) VALUES (
                '{payment_intent.id}',
                {payment_intent.amount},
                '{payment_intent.currency}',
                'failed',
                '{payment_intent.payment_method}',
                '{payment_intent.receipt_email}',
                NOW(),
                NOW()
            )
        """)
        
        # Schedule retry logic
        await schedule_payment_retry(payment_intent.id)
    except Exception as e:
        raise Exception(f"Failed to record failed payment: {str(e)}")

async def schedule_payment_retry(payment_id: str) -> None:
    """Schedule payment retry."""
    try:
        await query_db(f"""
            INSERT INTO payment_retries (
                payment_id, attempt_count,
                next_attempt_at, status
            ) VALUES (
                '{payment_id}',
                0,
                NOW() + INTERVAL '1 day',
                'scheduled'
            )
        """)
    except Exception as e:
        raise Exception(f"Failed to schedule payment retry: {str(e)}")

async def handle_failed_invoice(invoice: Any) -> None:
    """Handle failed invoice payment."""
    try:
        subscription_id = invoice.subscription
        await query_db(f"""
            UPDATE subscriptions
            SET status = 'past_due',
                updated_at = NOW()
            WHERE id = '{subscription_id}'
        """)
        
        # Send dunning email
        await send_dunning_email(invoice.customer_email)
    except Exception as e:
        raise Exception(f"Failed to handle failed invoice: {str(e)}")

async def send_dunning_email(email: str) -> None:
    """Send dunning email for failed payments."""
    # TODO: Implement email sending logic
    pass

async def handle_get_invoices(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Get invoice history."""
    try:
        customer_id = query_params.get("customer_id")
        limit = int(query_params.get("limit", 10))
        offset = int(query_params.get("offset", 0))
        
        invoices = stripe.Invoice.list(
            customer=customer_id,
            limit=limit,
            offset=offset
        )
        
        return _make_response(200, {
            "invoices": invoices.data,
            "total": invoices.total_count
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to get invoices: {str(e)}")

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
