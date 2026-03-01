"""
Payment processing API for revenue vertical MVP.
Handles Stripe/PayPal transactions and digital fulfillment.
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import stripe
import paypalrestsdk

from core.database import query_db
from api.revenue_api import _make_response, _error_response

logger = logging.getLogger(__name__)

# Initialize payment processors
stripe.api_key = os.getenv('STRIPE_API_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_SECRET')
})

async def handle_payment_intent(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process payment from Stripe webhook"""
    try:
        payment_intent = event_data['data']['object']
        amount = payment_intent['amount'] / 100  # Convert cents to dollars
        email = payment_intent.get('receipt_email', '')

        # Record transaction
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {payment_intent['amount']},
                '{payment_intent['currency']}',
                'stripe',
                '{json.dumps({
                    'email': email,
                    'payment_id': payment_intent['id'],
                    'product': 'mvp_vertical'
                })}'::jsonb,
                NOW()
            )
        """)

        # Fulfill order (digital download or service activation)
        fulfillment_url = generate_fulfillment(email)
        
        return _make_response(200, {
            "status": "processed", 
            "email_sent": True,
            "fulfillment_url": fulfillment_url
        })
    
    except Exception as e:
        logger.error(f"Payment processing failed: {str(e)}")
        return _error_response(500, f"Payment processing failed: {str(e)}")

def generate_fulfillment(email: str) -> str:
    """Generate fulfillment for purchase"""
    # This could be:
    # 1. A unique download URL
    # 2. API access token
    # 3. Service activation
    return f"https://api.example.com/v1/access/{uuid.uuid4()}"

async def create_checkout_session(
    price_id: str, 
    success_url: str, 
    cancel_url: str
) -> Dict[str, Any]:
    """Create Stripe checkout session"""
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={'product': 'mvp_vertical'}
        )
        return _make_response(200, {"url": session.url})
    except Exception as e:
        return _error_response(500, str(e))

def route_request(path: str, method: str, query_params: Dict[str, Any], 
                 body: Optional[str] = None) -> Dict[str, Any]:
    """Route payment API requests"""
    if method == "OPTIONS":
        return _make_response(200, {})
    
    parts = [p for p in path.split("/") if p]
    
    # POST /payment/webhook
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "webhook":
        if body:
            return handle_payment_intent(json.loads(body))
        return _error_response(400, "Webhook requires body")
    
    # GET /payment/checkout
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "checkout":
        return create_checkout_session(
            query_params.get('price_id'),
            query_params.get('success_url'),
            query_params.get('cancel_url')
        )
    
    return _error_response(404, "Not found")

__all__ = ["route_request"]
