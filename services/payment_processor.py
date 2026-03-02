"""Handle payment processing with Stripe/PayPal integration."""
import os
import stripe
import paypalrestsdk
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from core.database import query_db

class PaymentProcessor:
    def __init__(self):
        self.stripe_key = os.getenv("STRIPE_SECRET_KEY")
        self.paypal_mode = os.getenv("PAYPAL_MODE", "sandbox")
        self.paypal_client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.paypal_secret = os.getenv("PAYPAL_SECRET")
        
        stripe.api_key = self.stripe_key
        paypalrestsdk.configure({
            "mode": self.paypal_mode,
            "client_id": self.paypal_client_id,
            "client_secret": self.paypal_secret
        })

    async def create_payment_intent(
        self, 
        amount: int, 
        currency: str = "usd",
        payment_method: str = "stripe",
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create payment intent with optional payment method."""
        try:
            if payment_method == "stripe":
                intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency=currency,
                    metadata=metadata or {},
                )
                return {"success": True, "client_secret": intent.client_secret}
            
            elif payment_method == "paypal":
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {"total": str(amount/100), "currency": currency},
                        "description": "Purchase"
                    }],
                    "redirect_urls": {
                        "return_url": os.getenv("PAYPAL_RETURN_URL"),
                        "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                    }
                })
                if payment.create():
                    return {"success": True, "approval_url": next(
                        link.href for link in payment.links if link.rel == "approval_url"
                    )}
                return {"success": False, "error": payment.error}
            
            return {"success": False, "error": "Invalid payment method"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def confirm_payment(
        self, 
        payment_id: str, 
        payment_method: str,
        payer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Confirm a payment and record transaction."""
        try:
            if payment_method == "stripe":
                intent = stripe.PaymentIntent.retrieve(payment_id)
                if intent.status == "succeeded":
                    await self._record_transaction(
                        amount=intent.amount,
                        currency=intent.currency,
                        payment_id=intent.id,
                        method="stripe",
                        metadata=intent.metadata
                    )
                    return {"success": True, "status": intent.status}
            
            elif payment_method == "paypal" and payer_id:
                payment = paypalrestsdk.Payment.find(payment_id)
                if payment.execute({"payer_id": payer_id}):
                    await self._record_transaction(
                        amount = int(float(payment.transactions[0].amount.total)*100),
                        currency=payment.transactions[0].amount.currency,
                        payment_id=payment.id,
                        method="paypal"
                    )
                    return {"success": True, "status": payment.state}
            
            return {"success": False, "error": "Payment not completed"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _record_transaction(
        self,
        amount: int,
        currency: str,
        payment_id: str,
        method: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """Record successful transaction in database."""
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(), 'revenue', {amount}, '{currency}',
                '{method}', '{json.dumps(metadata or {})}', NOW(), NOW()
            )
            """
        )
