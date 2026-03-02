from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from payment_processor import PaymentProcessor
import logging

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

processor = PaymentProcessor()

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        result = await processor.handle_webhook(
            payload.decode("utf-8"),
            sig_header,
            os.getenv("STRIPE_WEBHOOK_SECRET")
        )
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"status": "success"}
    except Exception as e:
        logging.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/webhook/paypal")
async def paypal_webhook(request: Request):
    payload = await request.json()
    # Validate PayPal webhook
    # Process PayPal events
    return {"status": "success"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
