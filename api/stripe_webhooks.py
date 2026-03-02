"""
Stripe Webhook Handlers - Process payment events and manage subscriptions.
"""

import json
import stripe
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db

stripe.api_key = "sk_test_..."  # Should be from environment

async def handle_stripe_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process Stripe webhook event."""
    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})
    
    if event_type == "checkout.session.completed":
        # New subscription created
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")
        await create_customer_subscription(customer_id, subscription_id)
        
    elif event_type == "customer.subscription.updated":
        # Subscription status changed
        subscription_id = data.get("id")
        status = data.get("status")
        await update_subscription_status(subscription_id, status)
        
    elif event_type == "invoice.payment_succeeded":
        # Payment succeeded
        invoice_id = data.get("id")
        amount_paid = data.get("amount_paid")
        await record_payment(invoice_id, amount_paid)
        
    elif event_type == "invoice.payment_failed":
        # Payment failed
        customer_id = data.get("customer")
        await handle_payment_failure(customer_id)
        
    return {"success": True}

async def create_customer_subscription(customer_id: str, subscription_id: str) -> None:
    """Create new customer subscription."""
    try:
        # Get customer details from Stripe
        customer = stripe.Customer.retrieve(customer_id)
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        # Insert into database
        await query_db(f"""
            INSERT INTO customers (
                id, email, name, created_at, 
                subscription_id, subscription_status
            ) VALUES (
                '{customer_id}',
                '{customer.email}',
                '{customer.name}',
                '{datetime.now(timezone.utc).isoformat()}',
                '{subscription_id}',
                '{subscription.status}'
            )
        """)
        
        # Provision service
        await provision_service(customer_id)
        
    except Exception as e:
        print(f"Error creating subscription: {str(e)}")

async def update_subscription_status(subscription_id: str, status: str) -> None:
    """Update subscription status."""
    try:
        await query_db(f"""
            UPDATE customers
            SET subscription_status = '{status}'
            WHERE subscription_id = '{subscription_id}'
        """)
        
        if status in ["canceled", "unpaid"]:
            await deprovision_service(subscription_id)
            
    except Exception as e:
        print(f"Error updating subscription: {str(e)}")

async def record_payment(invoice_id: str, amount_paid: int) -> None:
    """Record successful payment."""
    try:
        await query_db(f"""
            INSERT INTO payments (
                id, amount_cents, currency, status,
                created_at, updated_at
            ) VALUES (
                '{invoice_id}',
                {amount_paid},
                'usd',
                'succeeded',
                NOW(),
                NOW()
            )
        """)
    except Exception as e:
        print(f"Error recording payment: {str(e)}")

async def handle_payment_failure(customer_id: str) -> None:
    """Handle payment failure."""
    try:
        await query_db(f"""
            UPDATE customers
            SET subscription_status = 'past_due'
            WHERE id = '{customer_id}'
        """)
        
        # Send automated email
        await send_email(customer_id, "payment_failed")
        
    except Exception as e:
        print(f"Error handling payment failure: {str(e)}")

async def provision_service(customer_id: str) -> None:
    """Provision service for new customer."""
    # Implementation depends on your service
    pass

async def deprovision_service(subscription_id: str) -> None:
    """Deprovision service for canceled subscription."""
    # Implementation depends on your service
    pass

async def send_email(customer_id: str, template: str) -> None:
    """Send automated email."""
    # Implementation depends on your email service
    pass
