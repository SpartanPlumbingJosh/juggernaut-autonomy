import os
import stripe
import paypalrestsdk
from typing import Dict, Any, Optional
from datetime import datetime
from core.database import execute_sql
from core.logging import log_action

# Initialize payment processors
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

class PaymentProcessor:
    """Handle payment processing through multiple gateways."""
    
    def __init__(self):
        self.gateways = {
            "stripe": self._process_stripe,
            "paypal": self._process_paypal
        }
    
    async def process_payment(self, gateway: str, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through specified gateway."""
        processor = self.gateways.get(gateway.lower())
        if not processor:
            return {"success": False, "error": f"Unsupported gateway: {gateway}"}
        
        try:
            result = await processor(payment_data)
            await self._record_transaction(result)
            return result
        except Exception as e:
            log_action("payment.failed", f"Payment failed: {str(e)}", level="error")
            return {"success": False, "error": str(e)}
    
    async def _process_stripe(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through Stripe."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(payment_data["amount"] * 100),  # Convert to cents
                currency=payment_data.get("currency", "usd"),
                payment_method=payment_data["payment_method"],
                confirmation_method="manual",
                confirm=True,
                metadata=payment_data.get("metadata", {})
            )
            
            if intent.status == "succeeded":
                return {
                    "success": True,
                    "transaction_id": intent.id,
                    "amount": intent.amount / 100,
                    "currency": intent.currency,
                    "gateway": "stripe"
                }
            return {"success": False, "error": f"Payment failed: {intent.status}"}
        except stripe.error.StripeError as e:
            raise Exception(f"Stripe error: {str(e)}")
    
    async def _process_paypal(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through PayPal."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": str(payment_data["amount"]),
                        "currency": payment_data.get("currency", "USD")
                    },
                    "description": payment_data.get("description", "")
                }],
                "redirect_urls": {
                    "return_url": payment_data.get("return_url", ""),
                    "cancel_url": payment_data.get("cancel_url", "")
                }
            })
            
            if payment.create():
                return {
                    "success": True,
                    "transaction_id": payment.id,
                    "amount": payment_data["amount"],
                    "currency": payment_data.get("currency", "USD"),
                    "gateway": "paypal"
                }
            return {"success": False, "error": payment.error}
        except Exception as e:
            raise Exception(f"PayPal error: {str(e)}")
    
    async def _record_transaction(self, result: Dict[str, Any]) -> None:
        """Record successful transaction in database."""
        if not result.get("success"):
            return
        
        await execute_sql(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(result["amount"] * 100)},
                '{result["currency"]}',
                '{result["gateway"]}',
                '{{"transaction_id": "{result["transaction_id"]}"}}'::jsonb,
                NOW(),
                NOW()
            )
        """)
        log_action("payment.success", f"Payment processed: {result['transaction_id']}")

async def handle_webhook(event: Dict[str, Any], gateway: str) -> Dict[str, Any]:
    """Handle payment gateway webhook events."""
    try:
        if gateway == "stripe":
            return await _handle_stripe_webhook(event)
        elif gateway == "paypal":
            return await _handle_paypal_webhook(event)
        return {"success": False, "error": "Unsupported gateway"}
    except Exception as e:
        log_action("webhook.error", f"Webhook failed: {str(e)}", level="error")
        return {"success": False, "error": str(e)}

async def _handle_stripe_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Stripe webhook events."""
    # Verify event signature
    try:
        stripe.Webhook.construct_event(
            event["body"],
            event["headers"]["Stripe-Signature"],
            os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except Exception as e:
        return {"success": False, "error": f"Signature verification failed: {str(e)}"}
    
    # Process event
    event_type = event["type"]
    data = event["data"]["object"]
    
    if event_type == "payment_intent.succeeded":
        await PaymentProcessor()._record_transaction({
            "success": True,
            "transaction_id": data["id"],
            "amount": data["amount"] / 100,
            "currency": data["currency"],
            "gateway": "stripe"
        })
        return {"success": True}
    
    return {"success": False, "error": "Unhandled event type"}

async def _handle_paypal_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle PayPal webhook events."""
    # Verify event signature
    try:
        paypalrestsdk.WebhookEvent.verify(
            event["headers"]["Paypal-Transmission-Id"],
            event["headers"]["Paypal-Transmission-Sig"],
            event["headers"]["Paypal-Transmission-Time"],
            os.getenv("PAYPAL_WEBHOOK_ID"),
            event["body"],
            os.getenv("PAYPAL_WEBHOOK_SECRET")
        )
    except Exception as e:
        return {"success": False, "error": f"Signature verification failed: {str(e)}"}
    
    # Process event
    event_type = event["event_type"]
    resource = event["resource"]
    
    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        await PaymentProcessor()._record_transaction({
            "success": True,
            "transaction_id": resource["id"],
            "amount": float(resource["amount"]["value"]),
            "currency": resource["amount"]["currency"],
            "gateway": "paypal"
        })
        return {"success": True}
    
    return {"success": False, "error": "Unhandled event type"}
