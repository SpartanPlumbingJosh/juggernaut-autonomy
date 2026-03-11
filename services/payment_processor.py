"""
Payment Processor - Handles Stripe and PayPal integrations for automated payments.
"""
import os
import stripe
import paypalrestsdk
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self):
        # Initialize Stripe
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        
        # Initialize PayPal
        paypalrestsdk.configure({
            "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
            "client_id": os.getenv('PAYPAL_CLIENT_ID'),
            "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
        })

    async def create_stripe_payment(self, amount: float, currency: str, metadata: Dict) -> Dict:
        """Create a Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                metadata=metadata,
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_id": intent.id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_paypal_payment(self, amount: float, currency: str, metadata: Dict) -> Dict:
        """Create a PayPal payment."""
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
                    "return_url": os.getenv('PAYPAL_RETURN_URL'),
                    "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                }
            })
            
            if payment.create():
                return {
                    "success": True,
                    "approval_url": payment.links[1].href,
                    "payment_id": payment.id
                }
            return {"success": False, "error": payment.error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def verify_payment(self, payment_id: str, provider: str) -> Dict:
        """Verify payment status."""
        try:
            if provider == "stripe":
                intent = stripe.PaymentIntent.retrieve(payment_id)
                return {
                    "success": True,
                    "paid": intent.status == "succeeded",
                    "amount": intent.amount / 100,
                    "currency": intent.currency,
                    "created": datetime.fromtimestamp(intent.created)
                }
            elif provider == "paypal":
                payment = paypalrestsdk.Payment.find(payment_id)
                return {
                    "success": True,
                    "paid": payment.state == "approved",
                    "amount": float(payment.transactions[0].amount.total),
                    "currency": payment.transactions[0].amount.currency,
                    "created": datetime.strptime(payment.create_time, "%Y-%m-%dT%H:%M:%SZ")
                }
            return {"success": False, "error": "Invalid provider"}
        except Exception as e:
            return {"success": False, "error": str(e)}
