"""
Payment Processor - Handle Stripe/PayPal payments and subscriptions
"""

import stripe
import paypalrestsdk
from typing import Dict, Any, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self, stripe_key: str, paypal_client_id: str, paypal_secret: str):
        self.stripe_key = stripe_key
        self.paypal_client_id = paypal_client_id
        self.paypal_secret = paypal_secret
        
        stripe.api_key = stripe_key
        paypalrestsdk.configure({
            "mode": "live",
            "client_id": paypal_client_id,
            "client_secret": paypal_secret
        })

    async def create_stripe_payment(self, amount: float, currency: str, customer_email: str) -> Dict[str, Any]:
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),
                currency=currency.lower(),
                receipt_email=customer_email,
                metadata={
                    "integration_check": "accept_a_payment"
                }
            )
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_id": intent.id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_paypal_payment(self, amount: float, currency: str, return_url: str, cancel_url: str) -> Dict[str, Any]:
        try:
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
                    "return_url": return_url,
                    "cancel_url": cancel_url
                }
            })
            
            if payment.create():
                return {
                    "success": True,
                    "approval_url": next(link.href for link in payment.links if link.rel == "approval_url"),
                    "payment_id": payment.id
                }
            else:
                return {"success": False, "error": payment.error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def fulfill_order(self, payment_id: str, payment_method: str) -> Dict[str, Any]:
        try:
            # Record payment in database
            # Trigger fulfillment workflow
            # Send confirmation email
            return {"success": True, "message": "Order fulfilled"}
        except Exception as e:
            return {"success": False, "error": str(e)}
