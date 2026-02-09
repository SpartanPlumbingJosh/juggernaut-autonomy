import os
import stripe
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

class PaymentSuccessRequest(BaseModel):
    session_id: str

@app.get("/success")
async def payment_success(request: Request):
    session_id = request.query_params.get('session_id')
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")
    
    try:
        # Verify the session with Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Here you would typically:
        # 1. Verify payment was successful
        # 2. Fulfill the order (send email, create account, etc.)
        # 3. Log the transaction
        
        return JSONResponse({
            "status": "success",
            "message": "Payment processed successfully",
            "download_url": "/download/your-product-file.zip",
            "receipt_url": session.get("receipt_url", "")
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Fulfill the purchase
        await fulfill_order(session)
    
    return JSONResponse({"status": "success"})

async def fulfill_order(session):
    """
    Fulfill the customer's order after payment confirmation
    """
    try:
        customer_email = session["customer_details"]["email"]
        amount_total = session["amount_total"] / 100  # Convert from cents
        
        # Here you would:
        # 1. Create a record in your database
        # 2. Send the digital product via email
        # 3. Trigger any post-purchase workflows
        
        print(f"Order fulfilled for {customer_email}, amount: {amount_total}")
        
    except Exception as e:
        print(f"Error fulfilling order: {str(e)}")
        raise

@app.get("/download/{file_name}")
async def download_file(file_name: str):
    """
    Securely serve the digital product file
    """
    # In production you would:
    # 1. Verify the user has purchased the product
    # 2. Log the download
    # 3. Serve from secure storage
    
    file_path = f"static/products/{file_name}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type='application/zip'
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
