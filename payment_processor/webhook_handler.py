"""
Webhook Handler - Processes payment gateway webhooks and triggers appropriate actions.
"""
import json
from typing import Any, Dict

from fastapi import FastAPI, Request, Response
from payment_processor import PaymentProcessor

app = FastAPI()
processor = PaymentProcessor()

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    result = await processor.handle_webhook(payload, signature, "stripe")
    return Response(status_code=200 if result["success"] else 400)

@app.post("/webhook/paypal")
async def paypal_webhook(request: Request):
    payload = await request.json()
    signature = request.headers.get("paypal-signature")
    result = await processor.handle_webhook(payload, signature, "paypal")
    return Response(status_code=200 if result["success"] else 400)
