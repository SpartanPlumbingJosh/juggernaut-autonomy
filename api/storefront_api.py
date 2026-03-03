"""
Digital Product Storefront API with Stripe integration.
Handles product listings, purchases, and webhook events.
"""

import json
import stripe
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import query_db
from api.revenue_api import _make_response, _error_response

# Initialize Stripe
stripe.api_key = "sk_test_..."  # Should be from config
WEBHOOK_SECRET = "whsec_..."    # Should be from config

# Product catalog
PRODUCTS = [
    {
        "id": "prod_1",
        "name": "Basic Report",
        "description": "Standard market analysis report",
        "price_cents": 1999,
        "delivery_type": "email"
    },
    {
        "id": "prod_2", 
        "name": "Premium Report",
        "description": "Detailed market analysis with recommendations",
        "price_cents": 4999,
        "delivery_type": "email"
    }
]

async def handle_list_products() -> Dict[str, Any]:
    """Get available products."""
    try:
        return _make_response(200, {"products": PRODUCTS})
    except Exception as e:
        return _error_response(500, f"Failed to fetch products: {str(e)}")

async def handle_create_checkout(product_id: str, customer_email: str) -> Dict[str, Any]:
    """Create Stripe checkout session."""
    try:
        product = next((p for p in PRODUCTS if p["id"] == product_id), None)
        if not product:
            return _error_response(404, "Product not found")

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': product["name"],
                        'description': product["description"],
                    },
                    'unit_amount': product["price_cents"],
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='https://yourdomain.com/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://yourdomain.com/cancel',
            customer_email=customer_email,
            metadata={
                "product_id": product_id,
                "delivery_type": product["delivery_type"]
            }
        )

        return _make_response(200, {
            "checkout_url": session.url,
            "session_id": session.id
        })
    except Exception as e:
        return _error_response(500, f"Failed to create checkout: {str(e)}")

async def handle_stripe_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """Process Stripe webhook events."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )

        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            await _record_payment(session)

        return _make_response(200, {"status": "processed"})
    except ValueError as e:
        return _error_response(400, f"Invalid payload: {str(e)}")
    except stripe.error.SignatureVerificationError as e:
        return _error_response(400, f"Invalid signature: {str(e)}")
    except Exception as e:
        return _error_response(500, f"Webhook error: {str(e)}")

async def _record_payment(session: Dict[str, Any]) -> None:
    """Record successful payment in revenue system."""
    amount_cents = session.get("amount_total", 0)
    product_id = session.get("metadata", {}).get("product_id")
    customer_email = session.get("customer_email", "")

    await query_db(f"""
        INSERT INTO revenue_events (
            id, event_type, amount_cents, currency, 
            source, metadata, recorded_at, created_at
        ) VALUES (
            gen_random_uuid(),
            'revenue',
            {amount_cents},
            'usd',
            'storefront',
            '{{"product_id": "{product_id}", "customer_email": "{customer_email}"}}'::jsonb,
            NOW(),
            NOW()
        )
    """)

def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route storefront API requests."""
    if method == "OPTIONS":
        return _make_response(200, {})

    parts = [p for p in path.split("/") if p]

    # GET /storefront/products
    if len(parts) == 2 and parts[0] == "storefront" and parts[1] == "products":
        return handle_list_products()

    # POST /storefront/checkout
    if len(parts) == 2 and parts[0] == "storefront" and parts[1] == "checkout":
        if not body:
            return _error_response(400, "Missing request body")
        try:
            data = json.loads(body)
            return handle_create_checkout(
                data.get("product_id"),
                data.get("customer_email")
            )
        except json.JSONDecodeError:
            return _error_response(400, "Invalid JSON")

    # POST /storefront/webhook
    if len(parts) == 2 and parts[0] == "storefront" and parts[1] == "webhook":
        if not body:
            return _error_response(400, "Missing payload")
        sig_header = query_params.get("stripe-signature", [""])[0]
        return handle_stripe_webhook(body.encode(), sig_header)

    return _error_response(404, "Not found")

__all__ = ["route_request"]
