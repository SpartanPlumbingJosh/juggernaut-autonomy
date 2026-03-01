from fastapi import FastAPI, Request, HTTPException
from payment_processor.payment_manager import PaymentManager
from payment_processor.models import Customer, Subscription, Payment, Invoice

app = FastAPI()
manager = PaymentManager()

@app.post("/customers")
async def create_customer(customer: Customer):
    result = await manager.create_customer(
        email=customer.email,
        name=customer.name,
        metadata=customer.metadata
    )
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('error'))
    return result

@app.post("/subscriptions")
async def create_subscription(subscription: Subscription):
    result = await manager.create_subscription(
        customer_id=subscription.customer_id,
        plan_id=subscription.plan_id
    )
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('error'))
    return result

@app.post("/webhooks/stripe")
async def handle_stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    result = await manager.handle_webhook(payload, sig_header)
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('error'))
    return {"success": True}

@app.get("/payments/{payment_id}")
async def get_payment(payment_id: str):
    # Implement payment retrieval logic
    pass

@app.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    # Implement invoice retrieval logic
    pass
