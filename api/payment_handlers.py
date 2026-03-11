"""
Payment Webhook Handlers - Process payment events from Stripe, PayPal, etc.
Handles successful payments, failed payments, refunds, and subscription events.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db
from core.logging import log_action

async def handle_payment_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process payment webhook event."""
    event_type = event.get("type")
    event_id = event.get("id")
    data = event.get("data", {})
    
    try:
        # Log the raw event for audit
        await log_action(
            "payment.webhook_received",
            f"Received payment webhook: {event_type}",
            level="info",
            output_data=event
        )
        
        # Route to appropriate handler
        if event_type == "payment.succeeded":
            return await handle_successful_payment(data)
        elif event_type == "payment.failed":
            return await handle_failed_payment(data)
        elif event_type == "charge.refunded":
            return await handle_refund(data)
        elif event_type == "subscription.created":
            return await handle_subscription_created(data)
        elif event_type == "subscription.updated":
            return await handle_subscription_updated(data)
        elif event_type == "subscription.cancelled":
            return await handle_subscription_cancelled(data)
        else:
            return {"success": False, "error": f"Unhandled event type: {event_type}"}
            
    except Exception as e:
        await log_action(
            "payment.webhook_error",
            f"Failed to process payment webhook: {str(e)}",
            level="error",
            error_data={"event_id": event_id, "error": str(e)}
        )
        return {"success": False, "error": str(e)}

async def handle_successful_payment(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process successful payment."""
    payment_id = data.get("id")
    amount = data.get("amount") / 100  # Convert cents to dollars
    currency = data.get("currency")
    customer_id = data.get("customer")
    metadata = data.get("metadata", {})
    
    try:
        # Record revenue event
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount * 100},
                '{currency}',
                'payment',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
        """)
        
        # Deliver product/service
        delivery_result = await deliver_product(customer_id, metadata)
        
        if not delivery_result.get("success"):
            raise Exception(f"Delivery failed: {delivery_result.get('error')}")
            
        await log_action(
            "payment.success",
            f"Processed successful payment: {payment_id}",
            level="info",
            output_data={
                "payment_id": payment_id,
                "amount": amount,
                "currency": currency,
                "customer_id": customer_id
            }
        )
        
        return {"success": True, "payment_id": payment_id}
        
    except Exception as e:
        await log_action(
            "payment.processing_error",
            f"Failed to process payment: {str(e)}",
            level="error",
            error_data={"payment_id": payment_id, "error": str(e)}
        )
        return {"success": False, "error": str(e)}

async def handle_failed_payment(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process failed payment attempt."""
    payment_id = data.get("id")
    failure_code = data.get("failure_code")
    failure_message = data.get("failure_message")
    
    try:
        # Record failed payment event
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'failed_payment',
                0,
                'USD',
                'payment',
                '{json.dumps({
                    "payment_id": payment_id,
                    "failure_code": failure_code,
                    "failure_message": failure_message
                })}'::jsonb,
                NOW(),
                NOW()
            )
        """)
        
        await log_action(
            "payment.failed",
            f"Payment failed: {payment_id}",
            level="warning",
            output_data={
                "payment_id": payment_id,
                "failure_code": failure_code,
                "failure_message": failure_message
            }
        )
        
        return {"success": True, "payment_id": payment_id}
        
    except Exception as e:
        await log_action(
            "payment.failure_recording_error",
            f"Failed to record failed payment: {str(e)}",
            level="error",
            error_data={"payment_id": payment_id, "error": str(e)}
        )
        return {"success": False, "error": str(e)}

async def deliver_product(customer_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Deliver digital product/service to customer."""
    product_id = metadata.get("product_id")
    license_key = metadata.get("license_key")
    
    try:
        # Generate download links, license keys, etc
        # This is just a stub - implement actual delivery logic here
        delivery_data = {
            "download_url": f"https://download.example.com/{product_id}",
            "license_key": license_key,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        }
        
        await log_action(
            "product.delivered",
            f"Delivered product to customer: {customer_id}",
            level="info",
            output_data={
                "customer_id": customer_id,
                "product_id": product_id,
                "delivery_data": delivery_data
            }
        )
        
        return {"success": True, "delivery_data": delivery_data}
        
    except Exception as e:
        await log_action(
            "product.delivery_failed",
            f"Failed to deliver product: {str(e)}",
            level="error",
            error_data={"customer_id": customer_id, "error": str(e)}
        )
        return {"success": False, "error": str(e)}

async def handle_refund(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process refund event."""
    refund_id = data.get("id")
    amount = data.get("amount") / 100
    payment_id = data.get("payment_id")
    
    try:
        # Record refund event
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'refund',
                {-amount * 100},
                'USD',
                'payment',
                '{json.dumps({
                    "refund_id": refund_id,
                    "payment_id": payment_id
                })}'::jsonb,
                NOW(),
                NOW()
            )
        """)
        
        await log_action(
            "payment.refund",
            f"Processed refund: {refund_id}",
            level="info",
            output_data={
                "refund_id": refund_id,
                "amount": amount,
                "payment_id": payment_id
            }
        )
        
        return {"success": True, "refund_id": refund_id}
        
    except Exception as e:
        await log_action(
            "payment.refund_error",
            f"Failed to process refund: {str(e)}",
            level="error",
            error_data={"refund_id": refund_id, "error": str(e)}
        )
        return {"success": False, "error": str(e)}

async def handle_subscription_created(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process new subscription creation."""
    subscription_id = data.get("id")
    customer_id = data.get("customer")
    plan_id = data.get("plan_id")
    
    try:
        # Record subscription event
        await query_db(f"""
            INSERT INTO subscriptions (
                id, customer_id, plan_id, status,
                created_at, updated_at
            ) VALUES (
                '{subscription_id}',
                '{customer_id}',
                '{plan_id}',
                'active',
                NOW(),
                NOW()
            )
        """)
        
        await log_action(
            "subscription.created",
            f"Created new subscription: {subscription_id}",
            level="info",
            output_data={
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "plan_id": plan_id
            }
        )
        
        return {"success": True, "subscription_id": subscription_id}
        
    except Exception as e:
        await log_action(
            "subscription.creation_error",
            f"Failed to create subscription: {str(e)}",
            level="error",
            error_data={"subscription_id": subscription_id, "error": str(e)}
        )
        return {"success": False, "error": str(e)}

async def handle_subscription_updated(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process subscription update."""
    subscription_id = data.get("id")
    status = data.get("status")
    
    try:
        # Update subscription status
        await query_db(f"""
            UPDATE subscriptions
            SET status = '{status}',
                updated_at = NOW()
            WHERE id = '{subscription_id}'
        """)
        
        await log_action(
            "subscription.updated",
            f"Updated subscription: {subscription_id}",
            level="info",
            output_data={
                "subscription_id": subscription_id,
                "status": status
            }
        )
        
        return {"success": True, "subscription_id": subscription_id}
        
    except Exception as e:
        await log_action(
            "subscription.update_error",
            f"Failed to update subscription: {str(e)}",
            level="error",
            error_data={"subscription_id": subscription_id, "error": str(e)}
        )
        return {"success": False, "error": str(e)}

async def handle_subscription_cancelled(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process subscription cancellation."""
    subscription_id = data.get("id")
    
    try:
        # Mark subscription as cancelled
        await query_db(f"""
            UPDATE subscriptions
            SET status = 'cancelled',
                updated_at = NOW()
            WHERE id = '{subscription_id}'
        """)
        
        await log_action(
            "subscription.cancelled",
            f"Cancelled subscription: {subscription_id}",
            level="info",
            output_data={"subscription_id": subscription_id}
        )
        
        return {"success": True, "subscription_id": subscription_id}
        
    except Exception as e:
        await log_action(
            "subscription.cancellation_error",
            f"Failed to cancel subscription: {str(e)}",
            level="error",
            error_data={"subscription_id": subscription_id, "error": str(e)}
        )
        return {"success": False, "error": str(e)}
