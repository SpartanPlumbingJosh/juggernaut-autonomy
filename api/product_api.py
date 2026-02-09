from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from datetime import datetime, timezone
from services.payment_service import PaymentService
from services.auth_service import AuthService
from core.database import query_db

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Initialize services
payment_service = PaymentService(api_key="your_stripe_key")
auth_service = AuthService(secret_key="your_secret_key")

@app.post("/api/payment/create-checkout")
async def create_checkout(
    request: Request,
    price_id: str,
    token: str = Depends(oauth2_scheme)
):
    """Create checkout session for product"""
    try:
        # Verify user
        user_data = auth_service.decode_token(token)
        user_id = user_data.get("sub")
        
        # Create checkout session
        session = await payment_service.create_checkout_session(
            price_id=price_id,
            user_id=user_id,
            success_url=str(request.url_for("payment_success")),
            cancel_url=str(request.url_for("payment_cancel")),
            metadata={"product": "premium"}
        )
        
        return {"checkout_url": session.url}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/payment/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, "your_webhook_secret"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Handle successful payment
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        await payment_service.log_transaction(
            amount_cents=session['amount_total'],
            currency=session['currency'],
            source="stripe",
            user_id=session['metadata']['user_id'],
            metadata={
                "payment_intent": session['payment_intent'],
                "product": session['metadata'].get('product')
            }
        )

    return {"status": "success"}
