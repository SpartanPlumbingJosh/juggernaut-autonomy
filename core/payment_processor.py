"""
Payment processing integration for multiple payment gateways.
Supports Stripe, PayPal, and custom payment processors.
"""

from typing import Dict, Any, Optional
import stripe
import paypalrestsdk

class PaymentProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.stripe_key = config.get("stripe_secret_key")
        self.paypal_config = config.get("paypal")
        
        if self.stripe_key:
            stripe.api_key = self.stripe_key
            
        if self.paypal_config:
            paypalrestsdk.configure({
                "mode": self.paypal_config.get("mode", "sandbox"),
                "client_id": self.paypal_config.get("client_id"),
                "client_secret": self.paypal_config.get("client_secret")
            })

    async def create_payment_intent(self, amount: float, currency: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a payment intent with Stripe."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency,
                metadata=metadata or {}
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_paypal_order(self, amount: float, currency: str, return_url: str, cancel_url: str) -> Dict[str, Any]:
        """Create a PayPal order."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount:.2f}",
                        "currency": currency
                    }
                }],
                "redirect_urls": {
                    "return_url": return_url,
                    "cancel_url": cancel_url
                }
            })
            
            if payment.create():
                return {"success": True, "payment_id": payment.id, "approval_url": payment.links[1].href}
            return {"success": False, "error": "Failed to create PayPal payment"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def capture_payment(self, payment_id: str, amount: float, currency: str) -> Dict[str, Any]:
        """Capture a payment."""
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            if payment.execute({"payer_id": payment.payer.payer_info.payer_id}):
                return {"success": True, "transaction_id": payment.transactions[0].related_resources[0].sale.id}
            return {"success": False, "error": "Payment capture failed"}
        except Exception as e:
            return {"success": False, "error": str(e)}
