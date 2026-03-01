from fastapi import FastAPI, Request, HTTPException
from payment_processor.payment_manager import PaymentManager
import logging

app = FastAPI()
manager = PaymentManager()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get('stripe-signature')
    
    try:
        success = await manager.handle_webhook(payload, signature, "stripe")
        if not success:
            raise HTTPException(status_code=400, detail="Webhook handling failed")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Stripe webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/webhook/paypal")
async def paypal_webhook(request: Request):
    payload = await request.json()
    signature = request.headers.get('paypal-signature')
    
    try:
        success = await manager.handle_webhook(payload, signature, "paypal")
        if not success:
            raise HTTPException(status_code=400, detail="Webhook handling failed")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"PayPal webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
