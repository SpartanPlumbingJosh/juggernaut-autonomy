from fastapi import FastAPI, Request, HTTPException
from typing import Dict, Any
import hmac
import hashlib
from services.payment_gateway import PaymentGateway

app = FastAPI()

@app.post("/webhooks/stripe")
async def handle_stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        gateway = PaymentGateway()
        result = await gateway.handle_webhook(payload, sig_header)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/webhooks/paddle")
async def handle_paddle_webhook(request: Request):
    payload = await request.json()
    signature = request.headers.get("paddle-signature")
    
    # Verify Paddle webhook
    public_key = open("paddle_public_key.pem").read()
    # Verification logic here
    
    try:
        gateway = PaymentGateway()
        result = await gateway.handle_webhook(payload, signature)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
