"""
Payment Webhook Handler - Processes payment processor webhooks in a scalable way.
"""
from fastapi import APIRouter, Request  
from starlette.responses import JSONResponse
import stripe
import paypalrestsdk
from redis import Redis
from concurrent.futures import ThreadPoolExecutor

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=10)

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except stripe.error.SignatureVerificationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    # Process event in background worker
    executor.submit(process_stripe_event, event)
    return JSONResponse({"status": "received"})

def process_stripe_event(event: stripe.Event):
    """Process Stripe webhook event"""
    event_type = event["type"]
    
    if event_type == "invoice.paid":
        # Handle successful payment
        invoice = event["data"]["object"]
        handle_payment_success(
            invoice.subscription, 
            invoice.amount_paid,
            invoice.id
        )
    elif event_type == "invoice.payment_failed":
        # Handle failed payment
        invoice = event["data"]["object"]
        handle_payment_failure(
            invoice.subscription,
            invoice.attempt_count
        )
    elif event_type == "customer.subscription.deleted":
        # Handle subscription cancellation
        subscription = event["data"]["object"]
        handle_subscription_cancelled(subscription.id)
