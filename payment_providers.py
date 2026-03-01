"""Payment provider integration handlers."""

from typing import Any, Dict

from revenue_api import _make_response, _error_response
from database import log_event, fulfill_order

def handle_stripe_webhook(body: str) -> Dict[str, Any]:
    """Process Stripe payment webhook."""
    try:
        # Validate signature, parse payload
        # Example - handle checkout.session.completed
        data = json.loads(body)
        if data.get("type") == "checkout.session.completed":
            customer_id = data["data"]["object"].get("customer")
            amount = data["data"]["object"].get("amount_total", 0) / 100  # Convert cents to dollars
            order_id = data["data"]["object"].get("metadata", {}).get("order_id")
            
            # Record payment and trigger fulfillment
            event_id = log_event(
                event_type="payment_received",
                amount=amount,
                currency=data["data"]["object"].get("currency", "usd"),
                customer_id=customer_id,
                source="stripe",
                metadata={
                    "order_id": order_id,
                    "stripe_event_id": data.get("id")
                }
            )
            
            # Auto-fulfill order
            if order_id:
                fulfill_order(order_id, payment_event_id=event_id)

        return _make_response(200, {"status": "processed"})
    except Exception as e:
        return _error_response(400, f"Failed to process Stripe webhook: {str(e)}")

def handle_paypal_webhook(body: str) -> Dict[str, Any]:
    """Process PayPal payment webhook."""
    try:
        data = json.loads(body)
        event_type = data.get("event_type", "")
        
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            order_details = data.get("resource", {})
            amount = float(order_details.get("amount", {}).get("value", 0))
            order_id = order_details.get("custom_id")
            
            event_id = log_event(
                event_type="payment_received",
                amount=amount,
                currency=order_details.get("amount", {}).get("currency_code", "USD"),
                customer_id=order_details.get("payer", {}).get("payer_id"),
                source="paypal",
                metadata={
                    "order_id": order_id,
                    "paypal_event_id": data.get("id")
                }
            )
            
            if order_id:
                fulfill_order(order_id, payment_event_id=event_id)

        return _make_response(200, {"status": "processed"})
    except Exception as e:
        return _error_response(400, f"Failed to process PayPal webhook: {str(e)}")
