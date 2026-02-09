from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from core.payment_processor import PaymentProcessor
from core.subscription_manager import SubscriptionManager
import os

app = FastAPI()

# Initialize payment processor
stripe_key = os.getenv("STRIPE_SECRET_KEY")
payment_processor = PaymentProcessor(stripe_key)
subscription_manager = SubscriptionManager()

@app.post("/webhook")
async def handle_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        result = payment_processor.handle_webhook(
            payload.decode("utf-8"),
            sig_header,
            os.getenv("STRIPE_WEBHOOK_SECRET")
        )
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/create-subscription")
async def create_subscription(customer_id: str, price_id: str):
    try:
        # Create subscription in Stripe
        stripe_sub = payment_processor.create_subscription(customer_id, price_id)
        
        # Create subscription in our system
        await subscription_manager.create_subscription(
            customer_id=customer_id,
            plan_id=price_id
        )
        
        return {"success": True, "subscription_id": stripe_sub["id"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/create-payment-intent")
async def create_payment_intent(amount: int, currency: str, customer_id: str):
    try:
        intent = payment_processor.create_payment_intent(
            amount=amount,
            currency=currency,
            customer_id=customer_id
        )
        return {"client_secret": intent["client_secret"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/invoices/{invoice_id}/pdf")
async def get_invoice_pdf(invoice_id: str):
    try:
        pdf_bytes = payment_processor.generate_invoice_pdf(invoice_id)
        return Response(content=pdf_bytes, media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
