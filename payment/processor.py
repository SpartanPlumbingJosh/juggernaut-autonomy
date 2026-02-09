import os
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.database import query_db

# Initialize payment processors
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

class PaymentProcessor:
    """Handle payment processing and fulfillment."""
    
    async def create_payment_intent(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                metadata=metadata,
                automatic_payment_methods={"enabled": True},
            )
            return {"success": True, "client_secret": intent.client_secret}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
    
    async def create_paypal_order(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a PayPal order."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount:.2f}",
                        "currency": currency.upper()
                    },
                    "description": metadata.get("description", ""),
                    "custom": json.dumps(metadata)
                }],
                "redirect_urls": {
                    "return_url": os.getenv("PAYPAL_RETURN_URL"),
                    "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                }
            })
            
            if payment.create():
                return {"success": True, "approval_url": next(link.href for link in payment.links if link.rel == "approval_url")}
            return {"success": False, "error": payment.error}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def record_transaction(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record a completed transaction in the database."""
        try:
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, 
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {int(float(payment_data.get("amount")) * 100)},
                    '{payment_data.get("currency", "USD")}',
                    '{payment_data.get("source", "unknown")}',
                    '{json.dumps(payment_data.get("metadata", {}))}',
                    NOW(),
                    NOW()
                )
            """)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def fulfill_order(self, payment_id: str) -> Dict[str, Any]:
        """Handle order fulfillment after successful payment."""
        try:
            # TODO: Implement specific fulfillment logic
            return {"success": True, "message": "Order fulfilled"}
        except Exception as e:
            return {"success": False, "error": str(e)}
