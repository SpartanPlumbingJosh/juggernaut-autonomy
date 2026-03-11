"""
Payment API - Handle payment processing and webhooks.

Supported gateways:
- Stripe
- PayPal 
- Crypto (via Coinbase Commerce)
"""

import os
import json
import stripe
import paypalrestsdk
from coinbase_commerce.client import Client
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db

# Initialize payment gateways
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
})
coinbase_client = Client(api_key=os.getenv('COINBASE_API_KEY'))

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

async def handle_create_payment(payment_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a payment intent."""
    try:
        amount = int(float(payment_data.get('amount', 0)) * 100)  # Convert to cents
        currency = payment_data.get('currency', 'usd').lower()
        gateway = payment_data.get('gateway', 'stripe').lower()
        metadata = payment_data.get('metadata', {})
        
        if gateway == 'stripe':
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata
            )
            return _make_response(200, {
                'client_secret': intent.client_secret,
                'payment_id': intent.id,
                'gateway': 'stripe'
            })
            
        elif gateway == 'paypal':
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount/100:.2f}",
                        "currency": currency.upper()
                    }
                }],
                "redirect_urls": {
                    "return_url": os.getenv('PAYPAL_RETURN_URL'),
                    "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                }
            })
            if payment.create():
                return _make_response(200, {
                    'approval_url': payment.links[1].href,
                    'payment_id': payment.id,
                    'gateway': 'paypal'
                })
            else:
                return _error_response(400, payment.error)
                
        elif gateway == 'crypto':
            charge = coinbase_client.charge.create({
                'name': metadata.get('description', 'Payment'),
                'description': metadata.get('description', ''),
                'pricing_type': 'fixed_price',
                'local_price': {
                    'amount': f"{amount/100:.2f}",
                    'currency': currency.upper()
                },
                'metadata': metadata
            })
            return _make_response(200, {
                'checkout_url': charge['hosted_url'],
                'payment_id': charge['id'],
                'gateway': 'crypto'
            })
            
        else:
            return _error_response(400, 'Unsupported payment gateway')
            
    except Exception as e:
        return _error_response(500, f"Payment creation failed: {str(e)}")

async def handle_payment_webhook(event_data: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
    """Process payment webhook events."""
    try:
        gateway = headers.get('X-Gateway', 'stripe').lower()
        event = None
        
        if gateway == 'stripe':
            sig = headers.get('Stripe-Signature')
            event = stripe.Webhook.construct_event(
                json.dumps(event_data), sig, os.getenv('STRIPE_WEBHOOK_SECRET')
            )
            
        elif gateway == 'paypal':
            event = paypalrestsdk.notifications.WebhookEvent.verify(
                headers.get('PAYPAL-TRANSMISSION-SIG'),
                json.dumps(event_data),
                os.getenv('PAYPAL_WEBHOOK_ID')
            )
            
        elif gateway == 'crypto':
            event = event_data  # Coinbase sends raw JSON
            
        if not event:
            return _error_response(400, 'Invalid webhook event')
            
        # Record transaction
        payment_id = event.get('id') or event.get('payment_id')
        amount = event.get('amount') or event.get('amount_received')
        currency = event.get('currency', 'usd').lower()
        status = event.get('status', 'pending').lower()
        
        if status in ['succeeded', 'completed', 'confirmed']:
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, 
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {int(amount)},
                    '{currency}',
                    '{gateway}',
                    '{json.dumps(event)}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            
        return _make_response(200, {'status': 'processed'})
        
    except Exception as e:
        return _error_response(500, f"Webhook processing failed: {str(e)}")

async def handle_generate_invoice(payment_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an invoice for a payment."""
    try:
        payment_id = payment_data.get('payment_id')
        gateway = payment_data.get('gateway', 'stripe').lower()
        
        if gateway == 'stripe':
            invoice = stripe.Invoice.create(
                customer=payment_data.get('customer_id'),
                auto_advance=True,
                collection_method='send_invoice',
                days_until_due=30,
                metadata=payment_data.get('metadata', {})
            )
            return _make_response(200, {
                'invoice_id': invoice.id,
                'invoice_url': invoice.hosted_invoice_url,
                'status': invoice.status
            })
            
        elif gateway == 'paypal':
            invoice = paypalrestsdk.Invoice({
                "merchant_info": {
                    "email": os.getenv('PAYPAL_MERCHANT_EMAIL')
                },
                "billing_info": [{
                    "email": payment_data.get('customer_email')
                }],
                "items": [{
                    "name": payment_data.get('description', 'Invoice Item'),
                    "quantity": 1,
                    "unit_price": {
                        "currency": payment_data.get('currency', 'usd'),
                        "value": payment_data.get('amount')
                    }
                }],
                "note": payment_data.get('note', ''),
                "payment_term": {
                    "term_type": "NET_30"
                }
            })
            if invoice.create():
                return _make_response(200, {
                    'invoice_id': invoice.id,
                    'invoice_url': invoice.links[0].href,
                    'status': invoice.status
                })
            else:
                return _error_response(400, invoice.error)
                
        else:
            return _error_response(400, 'Invoice generation not supported for this gateway')
            
    except Exception as e:
        return _error_response(500, f"Invoice generation failed: {str(e)}")

def route_payment_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route payment API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # POST /payment/create
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "create" and method == "POST":
        return handle_create_payment(json.loads(body or "{}"))
    
    # POST /payment/webhook
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "webhook" and method == "POST":
        return handle_payment_webhook(json.loads(body or "{}"), dict(query_params))
    
    # POST /payment/invoice
    if len(parts) == 2 and parts[0] == "payment" and parts[1] == "invoice" and method == "POST":
        return handle_generate_invoice(json.loads(body or "{}"))
    
    return _error_response(404, "Not found")

__all__ = ["route_payment_request"]
