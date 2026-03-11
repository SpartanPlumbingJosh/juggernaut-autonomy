"""
Billing API - Handle payments, subscriptions and revenue tracking.

Endpoints:
- POST /billing/create-customer - Create customer account
- POST /billing/create-subscription - Create subscription
- POST /billing/webhook - Payment webhook handler
- GET /billing/customer/{id} - Get customer details
"""

import json
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db
from api.revenue_api import _make_response, _error_response

# Initialize payment gateways
stripe.api_key = "sk_test_..."  # TODO: Move to config
paypalrestsdk.configure({
    "mode": "sandbox",  # TODO: Move to config
    "client_id": "...",
    "client_secret": "..."
})

async def handle_create_customer(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create customer account in Stripe/PayPal."""
    try:
        email = body.get("email")
        name = body.get("name")
        if not email or not name:
            return _error_response(400, "Email and name are required")

        # Create Stripe customer
        stripe_customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        )

        # Create PayPal billing agreement
        paypal_agreement = paypalrestsdk.BillingAgreement({
            "name": f"{name}'s Agreement",
            "description": "Recurring payment agreement",
            "start_date": datetime.now(timezone.utc).isoformat(),
            "payer": {
                "payment_method": "paypal"
            },
            "plan": {
                "type": "MERCHANT"
            }
        })

        if paypal_agreement.create():
            # Store customer in database
            await query_db(f"""
                INSERT INTO customers (
                    id, email, name, 
                    stripe_customer_id, paypal_agreement_id,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{email.replace("'", "''")}',
                    '{name.replace("'", "''")}',
                    '{stripe_customer.id}',
                    '{paypal_agreement.id}',
                    NOW(),
                    NOW()
                )
            """)

            return _make_response(201, {
                "customer": {
                    "email": email,
                    "name": name,
                    "stripe_id": stripe_customer.id,
                    "paypal_id": paypal_agreement.id
                }
            })
        else:
            return _error_response(500, "Failed to create PayPal agreement")

    except Exception as e:
        return _error_response(500, f"Failed to create customer: {str(e)}")

async def handle_create_subscription(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create subscription for customer."""
    try:
        customer_id = body.get("customer_id")
        plan_id = body.get("plan_id")
        payment_method = body.get("payment_method", "stripe")
        
        if not customer_id or not plan_id:
            return _error_response(400, "Customer ID and plan ID are required")

        # Get customer details
        customer_res = await query_db(f"""
            SELECT stripe_customer_id, paypal_agreement_id
            FROM customers
            WHERE id = '{customer_id.replace("'", "''")}'
        """)
        customer = customer_res.get("rows", [{}])[0]
        if not customer:
            return _error_response(404, "Customer not found")

        if payment_method == "stripe":
            # Create Stripe subscription
            subscription = stripe.Subscription.create(
                customer=customer["stripe_customer_id"],
                items=[{"price": plan_id}],
                expand=["latest_invoice.payment_intent"]
            )
        else:
            # Create PayPal subscription
            subscription = paypalrestsdk.BillingAgreement.find(customer["paypal_agreement_id"])
            subscription.execute({"payer_id": customer_id})

        # Store subscription in database
        await query_db(f"""
            INSERT INTO subscriptions (
                id, customer_id, plan_id,
                status, payment_method,
                created_at, updated_at
            ) VALUES (
                gen_random_uuid(),
                '{customer_id.replace("'", "''")}',
                '{plan_id.replace("'", "''")}',
                'active',
                '{payment_method.replace("'", "''")}',
                NOW(),
                NOW()
            )
        """)

        return _make_response(201, {
            "subscription": {
                "id": subscription.id,
                "status": subscription.status,
                "payment_method": payment_method
            }
        })

    except Exception as e:
        return _error_response(500, f"Failed to create subscription: {str(e)}")

async def handle_payment_webhook(body: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
    """Handle payment webhooks from Stripe/PayPal."""
    try:
        event = None
        source = headers.get("X-Payment-Source", "stripe").lower()

        if source == "stripe":
            # Verify Stripe webhook signature
            sig_header = headers.get("Stripe-Signature")
            event = stripe.Webhook.construct_event(
                json.dumps(body), sig_header, stripe.api_key
            )
        else:
            # Verify PayPal webhook signature
            event = paypalrestsdk.WebhookEvent.verify(
                headers.get("Paypal-Transmission-Id"),
                headers.get("Paypal-Transmission-Sig"),
                headers.get("Paypal-Transmission-Time"),
                json.dumps(body)
            )

        if event:
            # Handle payment events
            if event.type == "payment_intent.succeeded":
                await _handle_payment_success(event.data.object)
            elif event.type == "invoice.payment_failed":
                await _handle_payment_failure(event.data.object)
            elif event.type == "customer.subscription.deleted":
                await _handle_subscription_cancellation(event.data.object)

            return _make_response(200, {"status": "processed"})
        else:
            return _error_response(400, "Invalid webhook signature")

    except Exception as e:
        return _error_response(500, f"Failed to process webhook: {str(e)}")

async def _handle_payment_success(payment: Dict[str, Any]) -> None:
    """Handle successful payment."""
    await query_db(f"""
        INSERT INTO revenue_events (
            id, event_type, amount_cents, currency,
            source, metadata, recorded_at, created_at
        ) VALUES (
            gen_random_uuid(),
            'revenue',
            {int(payment["amount"])},
            '{payment["currency"]}',
            'payment',
            '{json.dumps(payment)}',
            NOW(),
            NOW()
        )
    """)

async def _handle_payment_failure(payment: Dict[str, Any]) -> None:
    """Handle failed payment."""
    await query_db(f"""
        UPDATE subscriptions
        SET status = 'past_due',
            updated_at = NOW()
        WHERE id = '{payment["subscription"]}'
    """)

async def _handle_subscription_cancellation(subscription: Dict[str, Any]) -> None:
    """Handle subscription cancellation."""
    await query_db(f"""
        UPDATE subscriptions
        SET status = 'canceled',
            updated_at = NOW()
        WHERE id = '{subscription["id"]}'
    """)

async def handle_get_customer(customer_id: str) -> Dict[str, Any]:
    """Get customer details."""
    try:
        res = await query_db(f"""
            SELECT id, email, name, stripe_customer_id, paypal_agreement_id,
                   created_at, updated_at
            FROM customers
            WHERE id = '{customer_id.replace("'", "''")}'
        """)
        customer = res.get("rows", [{}])[0]
        if not customer:
            return _error_response(404, "Customer not found")

        return _make_response(200, {"customer": customer})
    except Exception as e:
        return _error_response(500, f"Failed to get customer: {str(e)}")

def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route billing API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # POST /billing/create-customer
    if len(parts) == 2 and parts[0] == "billing" and parts[1] == "create-customer" and method == "POST":
        return handle_create_customer(json.loads(body or "{}"))
    
    # POST /billing/create-subscription
    if len(parts) == 2 and parts[0] == "billing" and parts[1] == "create-subscription" and method == "POST":
        return handle_create_subscription(json.loads(body or "{}"))
    
    # POST /billing/webhook
    if len(parts) == 2 and parts[0] == "billing" and parts[1] == "webhook" and method == "POST":
        return handle_payment_webhook(json.loads(body or "{}"), query_params)
    
    # GET /billing/customer/{id}
    if len(parts) == 3 and parts[0] == "billing" and parts[1] == "customer" and method == "GET":
        return handle_get_customer(parts[2])
    
    return _error_response(404, "Not found")

__all__ = ["route_request"]
