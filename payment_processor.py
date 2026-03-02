import stripe
import paypalrestsdk
from typing import Dict, Any, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self):
        self.stripe = stripe
        self.paypal = paypalrestsdk
        
    async def create_stripe_customer(self, email: str, payment_method: str) -> Dict[str, Any]:
        """Create a Stripe customer and attach payment method."""
        try:
            customer = self.stripe.Customer.create(
                email=email,
                payment_method=payment_method,
                invoice_settings={'default_payment_method': payment_method}
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            return {"success": False, "error": str(e)}
        
    async def create_paypal_order(self, amount: float, currency: str) -> Dict[str, Any]:
        """Create PayPal order for payment authorization."""
        try:
            payment = self.paypal.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": str(amount),
                        "currency": currency
                    }
                }]
            })
            if payment.create():
                return {"success": True, "payment_id": payment.id}
            return {"success": False, "error": "Payment creation failed"}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def capture_payment(self, provider: str, payment_id: str) -> Dict[str, Any]:
        """Capture authorized payment."""
        try:
            if provider == "stripe":
                payment_intent = self.stripe.PaymentIntent.capture(payment_id)
                return {"success": True, "amount": payment_intent.amount}
            elif provider == "paypal":
                payment = self.paypal.Payment.find(payment_id)
                if payment.execute({"payer_id": payment.payer.payer_info.payer_id}):
                    return {"success": True, "amount": payment.transactions[0].amount.total}
            return {"success": False, "error": "Payment capture failed"}
        except Exception as e:
            return {"success": False, "error": str(e)}
