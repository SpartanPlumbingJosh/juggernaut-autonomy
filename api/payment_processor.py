import os
import stripe
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

async def create_checkout_session(user_id: str, price_id: str) -> Dict[str, Any]:
    """Create a Stripe checkout session"""
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f"{os.getenv('FRONTEND_URL')}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{os.getenv('FRONTEND_URL')}/cancel",
            metadata={
                'user_id': user_id
            }
        )
        return {
            "session_id": session.id,
            "url": session.url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def handle_webhook_event(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """Process Stripe webhook events"""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
        
        event_type = event['type']
        data = event['data']['object']
        
        # Handle different event types
        if event_type == 'checkout.session.completed':
            return await handle_checkout_complete(data)
        elif event_type == 'customer.subscription.updated':
            return await handle_subscription_update(data)
        elif event_type == 'invoice.payment_failed':
            return await handle_payment_failed(data)
        
        return {"status": "unhandled_event"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

async def handle_checkout_complete(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle successful checkout"""
    user_id = data['metadata']['user_id']
    subscription_id = data['subscription']
    
    # Update user status and subscription info
    # Implement your database update logic here
    
    return {
        "status": "success",
        "user_id": user_id,
        "subscription_id": subscription_id
    }

async def handle_subscription_update(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle subscription changes"""
    subscription_id = data['id']
    status = data['status']
    
    # Update subscription status
    # Implement your database update logic here
    
    return {
        "status": "updated",
        "subscription_id": subscription_id,
        "new_status": status
    }

async def handle_payment_failed(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle failed payments"""
    subscription_id = data['subscription']
    
    # Notify user and update status
    # Implement your notification logic here
    
    return {
        "status": "payment_failed",
        "subscription_id": subscription_id
    }
