"""
Webhook handlers for payment events.
"""

import json
import logging
from typing import Dict, Any

from fastapi import Request, Response
from billing.payment_service import PaymentService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def stripe_webhook(request: Request, payment_service: PaymentService) -> Response:
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        result = payment_service.handle_webhook(payload, sig_header, 'stripe')
        if result.get('success'):
            return Response(status_code=200)
        return Response(status_code=400, content=json.dumps(result))
    except Exception as e:
        logger.error(f"Stripe webhook error: {str(e)}")
        return Response(status_code=500, content=str(e))

async def paypal_webhook(request: Request, payment_service: PaymentService) -> Response:
    """Handle PayPal webhook events."""
    payload = await request.json()
    auth_algo = request.headers.get('paypal-auth-algo')
    cert_url = request.headers.get('paypal-cert-url')
    transmission_id = request.headers.get('paypal-transmission-id')
    transmission_sig = request.headers.get('paypal-transmission-sig')
    transmission_time = request.headers.get('paypal-transmission-time')
    
    try:
        # Verify and process PayPal webhook
        # Implementation depends on PayPal SDK
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"PayPal webhook error: {str(e)}")
        return Response(status_code=500, content=str(e))
