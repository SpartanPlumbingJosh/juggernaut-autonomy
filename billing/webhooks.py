"""
Webhook handlers for billing system.
"""
from typing import Dict, Any
from fastapi import Request, HTTPException
from billing.service import BillingService

billing_service = BillingService()

async def stripe_webhook(request: Request) -> Dict[str, Any]:
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        if billing_service.handle_webhook(payload, sig_header, 'stripe'):
            return {'status': 'success'}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    raise HTTPException(status_code=400, detail='Invalid event')

async def paypal_webhook(request: Request) -> Dict[str, Any]:
    """Handle PayPal webhook events"""
    payload = await request.json()
    auth_algo = request.headers.get('paypal-auth-algo')
    cert_url = request.headers.get('paypal-cert-url')
    transmission_id = request.headers.get('paypal-transmission-id')
    transmission_sig = request.headers.get('paypal-transmission-sig')
    transmission_time = request.headers.get('paypal-transmission-time')
    
    try:
        if billing_service.handle_webhook(payload, transmission_sig, 'paypal'):
            return {'status': 'success'}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    raise HTTPException(status_code=400, detail='Invalid event')
