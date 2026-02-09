import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.database import query_db

class PaymentProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.stripe_key = config.get("stripe_secret_key")
        self.paypal_mode = config.get("paypal_mode", "sandbox")
        self.paypal_client_id = config.get("paypal_client_id")
        self.paypal_secret = config.get("paypal_secret")
        
        stripe.api_key = self.stripe_key
        paypalrestsdk.configure({
            "mode": self.paypal_mode,
            "client_id": self.paypal_client_id,
            "client_secret": self.paypal_secret
        })

    async def create_stripe_payment_intent(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                metadata=metadata,
                automatic_payment_methods={"enabled": True}
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_paypal_order(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount:.2f}",
                        "currency": currency.upper()
                    },
                    "description": metadata.get("description", "Service Payment")
                }],
                "redirect_urls": {
                    "return_url": metadata.get("return_url", ""),
                    "cancel_url": metadata.get("cancel_url", "")
                }
            })
            
            if payment.create():
                return {"success": True, "approval_url": next(link.href for link in payment.links if link.method == "REDIRECT")}
            return {"success": False, "error": "Failed to create PayPal order"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def record_transaction(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            sql = """
            INSERT INTO revenue_events (
                id, experiment_id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                %(experiment_id)s,
                'revenue',
                %(amount_cents)s,
                %(currency)s,
                %(source)s,
                %(metadata)s,
                NOW(),
                NOW()
            )
            """
            await query_db(sql, {
                "experiment_id": payment_data.get("experiment_id"),
                "amount_cents": int(payment_data.get("amount") * 100),
                "currency": payment_data.get("currency"),
                "source": payment_data.get("source"),
                "metadata": json.dumps(payment_data.get("metadata", {}))
            })
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
