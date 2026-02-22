import os
import stripe
import paypalrestsdk
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from core.database import query_db

# Initialize payment gateways
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_SECRET")
})

class PaymentGateway:
    """Handles payment processing and webhook integration."""
    
    def __init__(self):
        self.retry_count = 3
        self.retry_delay = 2  # seconds
        
    async def create_payment(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payment intent."""
        try:
            # Convert amount to smallest currency unit
            amount_cents = int(amount * 100)
            
            # Try Stripe first
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata,
                payment_method_types=["card"],
                capture_method="automatic"
            )
            
            return {
                "success": True,
                "payment_id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "gateway": "stripe"
            }
        except stripe.error.StripeError as e:
            # Fallback to PayPal
            try:
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": f"{amount:.2f}",
                            "currency": currency
                        },
                        "description": metadata.get("description", "")
                    }],
                    "redirect_urls": {
                        "return_url": os.getenv("PAYPAL_RETURN_URL"),
                        "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                    }
                })
                
                if payment.create():
                    return {
                        "success": True,
                        "payment_id": payment.id,
                        "approval_url": next(link.href for link in payment.links if link.method == "REDIRECT"),
                        "gateway": "paypal"
                    }
                raise Exception(payment.error)
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "gateway": "paypal"
                }
    
    async def handle_webhook(self, payload: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        """Process payment webhook events."""
        try:
            event = None
            
            # Determine gateway from payload
            if signature and "stripe" in payload.get("type", ""):
                event = stripe.Webhook.construct_event(
                    payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET")
                )
            elif "event_type" in payload and "paypal" in payload.get("event_type", ""):
                event = payload
            
            if not event:
                return {"success": False, "error": "Unknown webhook source"}
            
            # Process event
            if event.get("type") == "payment_intent.succeeded" or event.get("event_type") == "PAYMENT.SALE.COMPLETED":
                payment_data = event.get("data", {}).get("object", {}) if "stripe" in event.get("type", "") else event.get("resource", {})
                
                await query_db(f"""
                    INSERT INTO revenue_events (
                        id, event_type, amount_cents, currency, source,
                        metadata, recorded_at, created_at
                    ) VALUES (
                        gen_random_uuid(),
                        'revenue',
                        {int(float(payment_data.get("amount", 0)) * 100)},
                        '{payment_data.get("currency", "").lower()}',
                        'payment_gateway',
                        '{json.dumps(payment_data)}'::jsonb,
                        NOW(),
                        NOW()
                    )
                """)
                
                return {"success": True, "processed": True}
            
            return {"success": True, "processed": False}
        except Exception as e:
            return {"success": False, "error": str(e)}
