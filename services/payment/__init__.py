"""
Payment Service - Handles payment processing and gateway integrations.
"""
from typing import Optional, Dict, Any
import stripe
import paypalrestsdk

class PaymentService:
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

    async def create_payment_intent(self, amount: int, currency: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a payment intent with Stripe."""
        if not self.stripe_key:
            raise ValueError("Stripe integration not configured")
            
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def create_paypal_order(self, amount: str, currency: str) -> Dict[str, Any]:
        """Create a PayPal order."""
        if not self.paypal_config:
            raise ValueError("PayPal integration not configured")
            
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "transactions": [{
                    "amount": {
                        "total": amount,
                        "currency": currency
                    }
                }]
            })
            
            if payment.create():
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "approval_url": next(link.href for link in payment.links if link.method == "REDIRECT")
                }
            return {
                "success": False,
                "error": payment.error
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def capture_payment(self, payment_id: str, provider: str) -> Dict[str, Any]:
        """Capture a payment."""
        if provider == "stripe":
            try:
                intent = stripe.PaymentIntent.capture(payment_id)
                return {
                    "success": True,
                    "status": intent.status,
                    "amount_received": intent.amount_received
                }
            except stripe.error.StripeError as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        elif provider == "paypal":
            try:
                payment = paypalrestsdk.Payment.find(payment_id)
                if payment.execute({"payer_id": payment.payer.payer_info.payer_id}):
                    return {
                        "success": True,
                        "status": payment.state,
                        "amount": payment.transactions[0].amount.total
                    }
                return {
                    "success": False,
                    "error": payment.error
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        else:
            return {
                "success": False,
                "error": f"Unknown payment provider: {provider}"
            }
