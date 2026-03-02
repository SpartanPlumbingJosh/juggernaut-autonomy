"""
Payment Processor - Handle Stripe/PayPal webhooks and payment processing.
"""

import json
import stripe
from datetime import datetime
from typing import Any, Dict, Optional

from core.database import query_db

# Initialize Stripe
stripe.api_key = "sk_test_..."  # Should be from environment variables

async def handle_stripe_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process Stripe webhook events."""
    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})
    
    try:
        if event_type == "payment_intent.succeeded":
            # Payment succeeded - create order and trigger fulfillment
            payment_intent = data
            amount = payment_intent.get("amount")  # In cents
            currency = payment_intent.get("currency")
            customer_email = payment_intent.get("receipt_email")
            metadata = payment_intent.get("metadata", {})
            
            # Create order record
            order_id = await create_order(
                amount=amount,
                currency=currency,
                customer_email=customer_email,
                payment_method="stripe",
                payment_id=payment_intent.get("id"),
                metadata=metadata
            )
            
            # Trigger fulfillment
            await fulfill_order(order_id)
            
            return {"status": "success", "order_id": order_id}
            
        elif event_type == "charge.refunded":
            # Handle refunds
            charge = data
            await update_order_status(
                payment_id=charge.get("payment_intent"),
                status="refunded"
            )
            return {"status": "success"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    return {"status": "ignored"}

async def create_order(
    amount: int,
    currency: str,
    customer_email: str,
    payment_method: str,
    payment_id: str,
    metadata: Dict[str, Any]
) -> str:
    """Create a new order record."""
    try:
        result = await query_db(f"""
            INSERT INTO orders (
                id, amount, currency, customer_email,
                payment_method, payment_id, status,
                created_at, metadata
            ) VALUES (
                gen_random_uuid(),
                {amount},
                '{currency}',
                '{customer_email}',
                '{payment_method}',
                '{payment_id}',
                'pending',
                NOW(),
                '{json.dumps(metadata)}'::jsonb
            )
            RETURNING id
        """)
        return result.get("rows", [{}])[0].get("id")
    except Exception as e:
        raise Exception(f"Failed to create order: {str(e)}")

async def fulfill_order(order_id: str) -> None:
    """Trigger order fulfillment."""
    try:
        # Get order details
        order = await query_db(f"""
            SELECT * FROM orders WHERE id = '{order_id}'
        """)
        order_data = order.get("rows", [{}])[0]
        
        # TODO: Implement specific fulfillment logic based on product/service
        # This could include:
        # - Sending digital product access
        # - Triggering service delivery
        # - Adding user to subscription
        
        # Update order status
        await query_db(f"""
            UPDATE orders SET status = 'fulfilled', fulfilled_at = NOW()
            WHERE id = '{order_id}'
        """)
        
    except Exception as e:
        await query_db(f"""
            UPDATE orders SET status = 'failed', error = '{str(e)}'
            WHERE id = '{order_id}'
        """)
        raise

async def update_order_status(payment_id: str, status: str) -> None:
    """Update order status based on payment ID."""
    await query_db(f"""
        UPDATE orders SET status = '{status}'
        WHERE payment_id = '{payment_id}'
    """)

async def handle_paypal_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process PayPal webhook events."""
    # Similar implementation to Stripe webhook handler
    # Would handle PayPal-specific events like payment.capture.completed
    pass

__all__ = ["handle_stripe_webhook", "handle_paypal_webhook"]
