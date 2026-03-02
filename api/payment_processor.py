"""
Payment Processing API - Handle SaaS subscriptions and payments.

Features:
- Stripe integration for payment processing
- Subscription management
- Payment failure handling
- Webhook endpoints
"""

import os
import stripe
from datetime import datetime
from typing import Any, Dict, Optional

from core.database import query_db
from api.revenue_api import _make_response, _error_response

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

async def create_customer(email: str, name: str) -> Dict[str, Any]:
    """Create a new Stripe customer."""
    try:
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={"created_at": datetime.utcnow().isoformat()}
        )
        
        # Store customer in our database
        await query_db(f"""
            INSERT INTO customers (stripe_id, email, name, created_at)
            VALUES ('{customer.id}', '{email}', '{name}', NOW())
        """)
        
        return _make_response(200, {"customer_id": customer.id})
        
    except stripe.error.StripeError as e:
        return _error_response(500, f"Payment processing error: {str(e)}")
    except Exception as e:
        return _error_response(500, f"Failed to create customer: {str(e)}")

async def create_subscription(customer_id: str, price_id: str) -> Dict[str, Any]:
    """Create a new subscription."""
    try:
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"]
        )
        
        # Store subscription in database
        await query_db(f"""
            INSERT INTO subscriptions (stripe_id, customer_id, status, created_at)
            VALUES ('{subscription.id}', '{customer_id}', 'incomplete', NOW())
        """)
        
        return _make_response(200, {
            "subscription_id": subscription.id,
            "client_secret": subscription.latest_invoice.payment_intent.client_secret
        })
        
    except stripe.error.StripeError as e:
        return _error_response(500, f"Payment processing error: {str(e)}")
    except Exception as e:
        return _error_response(500, f"Failed to create subscription: {str(e)}")

async def handle_payment_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """Handle Stripe webhook events."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
        
        event_type = event['type']
        data = event['data']['object']
        
        if event_type == 'payment_intent.succeeded':
            await query_db(f"""
                UPDATE subscriptions
                SET status = 'active'
                WHERE stripe_id = '{data['subscription']}'
            """)
            
        elif event_type == 'payment_intent.payment_failed':
            await query_db(f"""
                UPDATE subscriptions
                SET status = 'failed'
                WHERE stripe_id = '{data['subscription']}'
            """)
            
        return _make_response(200, {"status": "success"})
        
    except stripe.error.SignatureVerificationError as e:
        return _error_response(400, "Invalid signature")
    except Exception as e:
        return _error_response(500, f"Webhook processing failed: {str(e)}")

def route_payment_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route payment API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # POST /payment/customer
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "customer" and method == "POST":
        return create_customer(body.get("email"), body.get("name"))
    
    # POST /payment/subscription
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "subscription" and method == "POST":
        return create_subscription(body.get("customer_id"), body.get("price_id"))
    
    # POST /payment/webhook
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "webhook" and method == "POST":
        return handle_payment_webhook(body, query_params.get("Stripe-Signature"))
    
    return _error_response(404, "Not found")

__all__ = ["route_payment_request"]
