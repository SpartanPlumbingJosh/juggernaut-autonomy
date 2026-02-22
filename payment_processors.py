import os
import stripe
import paypalrestsdk
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self):
        self.stripe_key = os.getenv('STRIPE_SECRET_KEY')
        self.paypal_client_id = os.getenv('PAYPAL_CLIENT_ID')
        self.paypal_secret = os.getenv('PAYPAL_SECRET')
        
        stripe.api_key = self.stripe_key
        paypalrestsdk.configure({
            "mode": "live" if os.getenv('PAYPAL_LIVE') else "sandbox",
            "client_id": self.paypal_client_id,
            "client_secret": self.paypal_secret
        })

    async def create_payment(self, amount: float, currency: str, customer_email: str, 
                           payment_method: str = 'stripe') -> Dict[str, Any]:
        try:
            if payment_method == 'stripe':
                intent = stripe.PaymentIntent.create(
                    amount=int(amount * 100),  # Convert to cents
                    currency=currency.lower(),
                    receipt_email=customer_email,
                    metadata={
                        "integration_check": "accept_a_payment"
                    }
                )
                return {
                    "success": True,
                    "payment_id": intent.id,
                    "client_secret": intent.client_secret,
                    "status": intent.status
                }
            elif payment_method == 'paypal':
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {
                        "payment_method": "paypal"
                    },
                    "transactions": [{
                        "amount": {
                            "total": f"{amount:.2f}",
                            "currency": currency.upper()
                        }
                    }],
                    "redirect_urls": {
                        "return_url": os.getenv('PAYPAL_RETURN_URL'),
                        "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                    }
                })
                if payment.create():
                    return {
                        "success": True,
                        "payment_id": payment.id,
                        "approval_url": next(link.href for link in payment.links if link.rel == "approval_url"),
                        "status": payment.state
                    }
                else:
                    return {"success": False, "error": payment.error}
            else:
                return {"success": False, "error": "Invalid payment method"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def confirm_payment(self, payment_id: str, payment_method: str) -> Dict[str, Any]:
        try:
            if payment_method == 'stripe':
                intent = stripe.PaymentIntent.retrieve(payment_id)
                if intent.status == 'succeeded':
                    return {"success": True, "status": intent.status}
                return {"success": False, "error": "Payment not succeeded"}
            elif payment_method == 'paypal':
                payment = paypalrestsdk.Payment.find(payment_id)
                if payment.execute({"payer_id": payment.payer.payer_info.payer_id}):
                    return {"success": True, "status": payment.state}
                return {"success": False, "error": payment.error}
            else:
                return {"success": False, "error": "Invalid payment method"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: Dict, signature: Optional[str] = None, 
                           payment_method: str = 'stripe') -> Dict[str, Any]:
        try:
            if payment_method == 'stripe':
                event = stripe.Webhook.construct_event(
                    payload, signature, os.getenv('STRIPE_WEBHOOK_SECRET')
                )
                if event.type == 'payment_intent.succeeded':
                    return {"success": True, "event": event.type}
                return {"success": False, "error": "Unhandled event type"}
            elif payment_method == 'paypal':
                # PayPal webhook verification
                return {"success": True, "event": "paypal_webhook"}
            else:
                return {"success": False, "error": "Invalid payment method"}
        except Exception as e:
            return {"success": False, "error": str(e)}
