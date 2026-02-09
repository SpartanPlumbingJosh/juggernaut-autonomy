import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db
from api.revenue_api import _make_response, _error_response

def process_payment_event(payment_data: Dict[str, Any], gateway: str) -> Dict[str, Any]:
    """Record payment in revenue events."""
    try:
        amount_cents = int(float(payment_data.get("amount", 0)) * 100)
        currency = payment_data.get("currency", "usd").lower()
        customer_id = payment_data.get("customer_id", "")
        metadata = {
            "gateway": gateway,
            "payment_id": payment_data.get("payment_id", ""),
            "customer_id": customer_id,
            "service_id": payment_data.get("service_id", ""),
            "invoice_id": payment_data.get("invoice_id", "")
        }
        
        sql = f"""
        INSERT INTO revenue_events (
            id, event_type, amount_cents, currency, source, metadata, recorded_at, created_at
        ) VALUES (
            gen_random_uuid(),
            'revenue',
            {amount_cents},
            '{currency}',
            '{gateway}',
            '{json.dumps(metadata)}'::jsonb,
            NOW(),
            NOW()
        )
        RETURNING id
        """
        
        result = await query_db(sql)
        event_id = result.get("rows", [{}])[0].get("id", "")
        
        return {"success": True, "event_id": event_id}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def handle_stripe_payment(body: Optional[str]) -> Dict[str, Any]:
    """Process Stripe payment."""
    try:
        if not body:
            return _error_response(400, "Missing payment data")
            
        payment_data = json.loads(body)
        
        # Verify Stripe payment
        stripe.api_key = "sk_test_..."  # Should be from config
        charge = stripe.Charge.retrieve(payment_data.get("charge_id"))
        
        if not charge.paid:
            return _error_response(400, "Payment not successful")
            
        # Record revenue event
        event_result = await process_payment_event({
            "amount": charge.amount / 100,
            "currency": charge.currency,
            "customer_id": charge.customer,
            "payment_id": charge.id,
            "service_id": payment_data.get("service_id", "")
        }, "stripe")
        
        if not event_result.get("success"):
            return _error_response(500, "Failed to record payment")
            
        # Trigger service delivery
        delivery_result = await deliver_service(
            customer_id=charge.customer,
            service_id=payment_data.get("service_id", ""),
            payment_id=charge.id
        )
        
        return _make_response(200, {
            "success": True,
            "payment_id": charge.id,
            "event_id": event_result.get("event_id"),
            "delivery": delivery_result
        })
        
    except Exception as e:
        return _error_response(500, f"Payment processing failed: {str(e)}")

async def handle_paypal_payment(body: Optional[str]) -> Dict[str, Any]:
    """Process PayPal payment."""
    try:
        if not body:
            return _error_response(400, "Missing payment data")
            
        payment_data = json.loads(body)
        
        # Verify PayPal payment
        paypalrestsdk.configure({
            "mode": "sandbox",  # Should be from config
            "client_id": "...",
            "client_secret": "..."
        })
        
        payment = paypalrestsdk.Payment.find(payment_data.get("payment_id"))
        
        if payment.state != "approved":
            return _error_response(400, "Payment not approved")
            
        # Record revenue event
        event_result = await process_payment_event({
            "amount": payment.transactions[0].amount.total,
            "currency": payment.transactions[0].amount.currency,
            "customer_id": payment_data.get("customer_id", ""),
            "payment_id": payment.id,
            "service_id": payment_data.get("service_id", "")
        }, "paypal")
        
        if not event_result.get("success"):
            return _error_response(500, "Failed to record payment")
            
        # Trigger service delivery
        delivery_result = await deliver_service(
            customer_id=payment_data.get("customer_id", ""),
            service_id=payment_data.get("service_id", ""),
            payment_id=payment.id
        )
        
        return _make_response(200, {
            "success": True,
            "payment_id": payment.id,
            "event_id": event_result.get("event_id"),
            "delivery": delivery_result
        })
        
    except Exception as e:
        return _error_response(500, f"Payment processing failed: {str(e)}")
