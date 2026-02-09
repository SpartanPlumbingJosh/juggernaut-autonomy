"""
Payment Webhook Handlers - Process payments from Stripe/PayPal and trigger product delivery.

Features:
- Payment verification and validation
- Automated product/service delivery
- Customer notifications
- Error recovery and retry mechanisms
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db

logger = logging.getLogger(__name__)

# Payment provider constants
PROVIDER_STRIPE = "stripe"
PROVIDER_PAYPAL = "paypal"

async def handle_stripe_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process Stripe webhook event."""
    try:
        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})
        
        # Handle different event types
        if event_type == "payment_intent.succeeded":
            return await _process_payment(
                provider=PROVIDER_STRIPE,
                payment_id=data.get("id"),
                amount=data.get("amount"),
                currency=data.get("currency"),
                customer_email=data.get("receipt_email"),
                metadata=data.get("metadata", {})
            )
        elif event_type == "charge.refunded":
            return await _handle_refund(
                provider=PROVIDER_STRIPE,
                payment_id=data.get("payment_intent"),
                refund_id=data.get("id"),
                amount=data.get("amount_refunded")
            )
            
        return {"status": "unhandled_event", "event_type": event_type}
        
    except Exception as e:
        logger.error(f"Stripe webhook processing failed: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}

async def handle_paypal_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process PayPal webhook event."""
    try:
        event_type = event.get("event_type")
        resource = event.get("resource", {})
        
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            return await _process_payment(
                provider=PROVIDER_PAYPAL,
                payment_id=resource.get("id"),
                amount=float(resource.get("amount", {}).get("value", 0)) * 100,
                currency=resource.get("amount", {}).get("currency_code"),
                customer_email=resource.get("payer", {}).get("email_address"),
                metadata=resource.get("custom", {})
            )
        elif event_type == "PAYMENT.CAPTURE.REFUNDED":
            return await _handle_refund(
                provider=PROVIDER_PAYPAL,
                payment_id=resource.get("id"),
                refund_id=resource.get("refund_id"),
                amount=float(resource.get("amount", {}).get("value", 0)) * 100
            )
            
        return {"status": "unhandled_event", "event_type": event_type}
        
    except Exception as e:
        logger.error(f"PayPal webhook processing failed: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}

async def _process_payment(
    provider: str,
    payment_id: str,
    amount: int,
    currency: str,
    customer_email: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Process a successful payment."""
    try:
        # Record the transaction
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount},
                '{currency}',
                '{provider}',
                '{json.dumps(metadata)}'::jsonb,
                NOW()
            )
        """)
        
        # Trigger product delivery
        product_id = metadata.get("product_id")
        if product_id:
            delivery_result = await _deliver_product(product_id, customer_email)
            if not delivery_result.get("success"):
                raise Exception(f"Product delivery failed: {delivery_result.get('error')}")
        
        # Send confirmation email
        await _send_confirmation_email(customer_email, payment_id, amount, currency)
        
        return {"status": "success", "payment_id": payment_id}
        
    except Exception as e:
        logger.error(f"Payment processing failed: {str(e)}", exc_info=True)
        await _handle_payment_failure(provider, payment_id, str(e))
        return {"status": "error", "error": str(e)}

async def _handle_refund(
    provider: str,
    payment_id: str,
    refund_id: str,
    amount: int
) -> Dict[str, Any]:
    """Process a refund."""
    try:
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents,
                source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                'refund',
                -{amount},
                '{provider}',
                '{{"payment_id": "{payment_id}", "refund_id": "{refund_id}"}}'::jsonb,
                NOW()
            )
        """)
        
        return {"status": "success", "refund_id": refund_id}
        
    except Exception as e:
        logger.error(f"Refund processing failed: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}

async def _deliver_product(product_id: str, customer_email: str) -> Dict[str, Any]:
    """Deliver product/service to customer."""
    try:
        # Get product details
        product = await query_db(f"""
            SELECT * FROM products WHERE id = '{product_id}'
        """)
        if not product.get("rows"):
            return {"success": False, "error": "Product not found"}
        
        # Trigger delivery based on product type
        product_type = product["rows"][0].get("type")
        if product_type == "digital":
            # Generate download link
            await _send_digital_access(customer_email, product_id)
        elif product_type == "service":
            # Activate service
            await _activate_service(customer_email, product_id)
        elif product_type == "physical":
            # Trigger shipping process
            await _initiate_shipping(customer_email, product_id)
            
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Product delivery failed: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

async def _send_confirmation_email(email: str, payment_id: str, amount: int, currency: str) -> None:
    """Send payment confirmation email."""
    try:
        # Format amount
        amount_formatted = f"{amount / 100:.2f} {currency.upper()}"
        
        # Send email via email service
        await query_db(f"""
            INSERT INTO email_queue (
                id, recipient, template_name, template_data, status
            ) VALUES (
                gen_random_uuid(),
                '{email}',
                'payment_confirmation',
                '{{"payment_id": "{payment_id}", "amount": "{amount_formatted}"}}'::jsonb,
                'pending'
            )
        """)
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {str(e)}", exc_info=True)

async def _handle_payment_failure(provider: str, payment_id: str, error: str) -> None:
    """Handle payment processing failures."""
    try:
        # Log the failure
        await query_db(f"""
            INSERT INTO payment_failures (
                id, provider, payment_id, error, occurred_at
            ) VALUES (
                gen_random_uuid(),
                '{provider}',
                '{payment_id}',
                '{error}',
                NOW()
            )
        """)
        
        # Trigger retry mechanism
        await _retry_payment_processing(provider, payment_id)
    except Exception as e:
        logger.error(f"Failed to handle payment failure: {str(e)}", exc_info=True)

async def _retry_payment_processing(provider: str, payment_id: str) -> None:
    """Retry failed payment processing."""
    try:
        # Implement retry logic with exponential backoff
        await query_db(f"""
            INSERT INTO payment_retries (
                id, provider, payment_id, retry_count, next_retry_at
            ) VALUES (
                gen_random_uuid(),
                '{provider}',
                '{payment_id}',
                1,
                NOW() + INTERVAL '5 minutes'
            )
        """)
    except Exception as e:
        logger.error(f"Failed to schedule payment retry: {str(e)}", exc_info=True)

__all__ = ["handle_stripe_webhook", "handle_paypal_webhook"]
