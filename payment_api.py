"""
Minimum Viable Payment Processor API
Integrates with Stripe and PayPal for rapid revenue generation.
"""
import os
import json
import logging
from typing import Dict, Any, Optional

import stripe
from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Payment Provider Configuration
class PaymentConfig:
    def __init__(self):
        self.stripe_key = os.getenv("STRIPE_SECRET_KEY")
        self.paypal_client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.paypal_secret = os.getenv("PAYPAL_SECRET")
        self.webhook_secret = os.getenv("WEBHOOK_SECRET")
        
        # Initialize providers
        stripe.api_key = self.stripe_key
        self.paypal_client = self._init_paypal()
    
    def _init_paypal(self) -> Optional[PayPalHttpClient]:
        if not self.paypal_client_id or not self.paypal_secret:
            return None
        environment = SandboxEnvironment(
            client_id=self.paypal_client_id,
            client_secret=self.paypal_secret
        )
        return PayPalHttpClient(environment)

payment_config = PaymentConfig()

# Core Payment Methods
async def process_payment(
    amount: float,
    currency: str,
    payment_method: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Process payment through selected provider."""
    try:
        amount_cents = int(amount * 100)  # Convert to smallest currency unit
        
        if payment_method == "stripe":
            # Stripe payment processing
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata,
                automatic_payment_methods={"enabled": True}
            )
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_id": intent.id
            }
            
        elif payment_method == "paypal" and payment_config.paypal_client:
            # PayPal payment processing
            from paypalcheckoutsdk.orders import OrdersCreateRequest
            request = OrdersCreateRequest()
            request.prefer("return=representation")
            request.request_body({
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": currency,
                        "value": str(amount)
                    },
                    "metadata": metadata
                }]
            })
            response = payment_config.paypal_client.execute(request)
            return {
                "success": True,
                "approval_url": next(
                    link.href for link in response.result.links 
                    if link.rel == "approve"
                ),
                "payment_id": response.result.id
            }
            
        else:
            raise HTTPException(status_code=400, detail="Unsupported payment method")
            
    except Exception as e:
        logger.error(f"Payment processing error: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail=f"Payment processing failed: {str(e)}"
        )

# API Endpoints
@app.post("/api/v1/payments/create")
async def create_payment(request: Request):
    """Create a new payment intent."""
    try:
        data = await request.json()
        amount = float(data.get("amount"))
        currency = data.get("currency", "usd").lower()
        payment_method = data.get("payment_method", "stripe").lower()
        
        if amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="Amount must be positive"
            )
        
        metadata = data.get("metadata", {})
        result = await process_payment(amount, currency, payment_method, metadata)
        return JSONResponse(result)
        
    except Exception as e:
        logger.error(f"Payment creation error: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail=f"Payment creation failed: {str(e)}"
        )

@app.post("/api/v1/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            payment_config.webhook_secret
        )
        
        # Handle payment events
        if event.type == "payment_intent.succeeded":
            payment = event.data.object
            logger.info(f"Payment succeeded: {payment.id}")
            # TODO: Process successful payment
            return JSONResponse({"success": True})
            
        return JSONResponse({"success": True})
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail=f"Webhook processing failed: {str(e)}"
        )

@app.post("/api/v1/webhooks/paypal")
async def paypal_webhook(request: Request):
    """Handle PayPal webhook events."""
    try:
        data = await request.json()
        event_id = data.get("id")
        
        # TODO: Verify webhook signature
        # TODO: Process payment events
        
        logger.info(f"Received PayPal webhook: {event_id}")
        return JSONResponse({"success": True})
        
    except Exception as e:
        logger.error(f"PayPal webhook error: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail=f"PayPal webhook processing failed: {str(e)}"
        )

def run_server():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    run_server()
