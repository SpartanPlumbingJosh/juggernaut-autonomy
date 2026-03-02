import os
import stripe
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

# Configure Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Revenue Product Service")

# Simple user auth (replace with your actual auth system)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class Product(BaseModel):
    id: str
    name: str
    description: str
    price_cents: int
    currency: str = "usd"
    metadata: Optional[Dict[str, Any]] = None

class PaymentIntent(BaseModel):
    id: str
    amount: int
    currency: str
    status: str
    client_secret: str

@app.post("/products/", response_model=Product)
async def create_product(product: Product):
    """Create a new product in Stripe"""
    try:
        stripe_product = stripe.Product.create(
            name=product.name,
            description=product.description,
            metadata=product.metadata or {}
        )
        
        stripe_price = stripe.Price.create(
            unit_amount=product.price_cents,
            currency=product.currency,
            product=stripe_product.id
        )
        
        return {
            "id": stripe_product.id,
            "name": stripe_product.name,
            "description": stripe_product.description,
            "price_cents": stripe_price.unit_amount,
            "currency": stripe_price.currency
        }
    except Exception as e:
        logger.error(f"Failed to create product: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/payment-intents/", response_model=PaymentIntent)
async def create_payment_intent(product_id: str):
    """Create a payment intent for a product"""
    try:
        # Get product price
        prices = stripe.Price.list(product=product_id, limit=1)
        if not prices.data:
            raise HTTPException(status_code=404, detail="Product not found")
        
        price = prices.data[0]
        
        # Create payment intent
        intent = stripe.PaymentIntent.create(
            amount=price.unit_amount,
            currency=price.currency,
            metadata={"product_id": product_id}
        )
        
        return {
            "id": intent.id,
            "amount": intent.amount,
            "currency": intent.currency,
            "status": intent.status,
            "client_secret": intent.client_secret
        }
    except Exception as e:
        logger.error(f"Failed to create payment intent: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/webhook/stripe/")
async def stripe_webhook(payload: bytes, stripe_signature: str):
    """Handle Stripe webhook events"""
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    event_type = event['type']
    data = event['data']
    
    if event_type == 'payment_intent.succeeded':
        payment_intent = data['object']
        handle_successful_payment(payment_intent)
    elif event_type == 'payment_intent.payment_failed':
        payment_intent = data['object']
        handle_failed_payment(payment_intent)
    else:
        logger.info(f"Unhandled event type: {event_type}")

    return {"status": "success"}

def handle_successful_payment(payment_intent: Dict[str, Any]):
    """Handle successful payment"""
    product_id = payment_intent['metadata'].get('product_id')
    amount = payment_intent['amount']
    currency = payment_intent['currency']
    
    # TODO: Implement fulfillment logic
    logger.info(f"Successful payment for product {product_id}: {amount} {currency}")
    
    # Record revenue event
    record_revenue_event(
        product_id=product_id,
        amount_cents=amount,
        currency=currency,
        event_type="revenue",
        source="stripe"
    )

def handle_failed_payment(payment_intent: Dict[str, Any]):
    """Handle failed payment"""
    product_id = payment_intent['metadata'].get('product_id')
    logger.warning(f"Payment failed for product {product_id}: {payment_intent['last_payment_error']}")

def record_revenue_event(
    product_id: str,
    amount_cents: int,
    currency: str,
    event_type: str,
    source: str
):
    """Record revenue event in database"""
    # TODO: Implement database recording
    logger.info(f"Recording revenue event: {event_type} for {product_id} ({amount_cents} {currency})")

def monitor_service():
    """Monitor service health and send alerts"""
    # TODO: Implement monitoring and alerting
    logger.info("Service monitoring check")
