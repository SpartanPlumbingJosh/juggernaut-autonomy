from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from billing.services import BillingService
from billing.models import PaymentMethod

app = FastAPI()

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get('stripe-signature')
    
    billing_service = BillingService(
        stripe_api_key="your_stripe_key",
        paypal_client_id="your_paypal_id",
        paypal_secret="your_paypal_secret"
    )
    
    try:
        success = await billing_service.handle_webhook(
            payload=payload,
            signature=signature,
            payment_method=PaymentMethod.STRIPE
        )
        if success:
            return JSONResponse(content={"status": "success"})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return JSONResponse(content={"status": "failed"}, status_code=400)

@app.post("/webhooks/paypal")
async def paypal_webhook(request: Request):
    payload = await request.json()
    billing_service = BillingService(
        stripe_api_key="your_stripe_key",
        paypal_client_id="your_paypal_id",
        paypal_secret="your_paypal_secret"
    )
    
    try:
        success = await billing_service.handle_webhook(
            payload=payload,
            signature="",
            payment_method=PaymentMethod.PAYPAL
        )
        if success:
            return JSONResponse(content={"status": "success"})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return JSONResponse(content={"status": "failed"}, status_code=400)
