import os
import stripe
import paypalrestsdk
from datetime import datetime
from typing import Dict, Optional, Tuple
from enum import Enum

class PaymentProvider(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"

class PaymentProcessor:
    def __init__(self):
        # Initialize payment gateways
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        paypalrestsdk.configure({
            "mode": os.getenv("PAYPAL_MODE", "sandbox"),
            "client_id": os.getenv("PAYPAL_CLIENT_ID"),
            "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
        })

    async def create_payment_intent(
        self,
        amount: float,
        currency: str,
        provider: PaymentProvider,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, Dict]:
        """Create payment intent with selected provider"""
        try:
            if provider == PaymentProvider.STRIPE:
                intent = stripe.PaymentIntent.create(
                    amount=int(amount * 100),  # Convert to cents
                    currency=currency.lower(),
                    metadata=metadata or {},
                    automatic_payment_methods={"enabled": True}
                )
                return True, {"payment_intent_id": intent.id, "client_secret": intent.client_secret}
            
            elif provider == PaymentProvider.PAYPAL:
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": str(amount),
                            "currency": currency.upper()
                        }
                    }],
                    "redirect_urls": {
                        "return_url": os.getenv("PAYPAL_RETURN_URL"),
                        "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                    }
                })
                if payment.create():
                    return True, {"payment_id": payment.id, "approval_url": payment.links[1].href}
                return False, {"error": payment.error}
            
            return False, {"error": "Invalid payment provider"}
        except Exception as e:
            return False, {"error": str(e)}

    async def verify_payment(
        self,
        payment_id: str,
        provider: PaymentProvider
    ) -> Tuple[bool, Dict]:
        """Verify payment status"""
        try:
            if provider == PaymentProvider.STRIPE:
                intent = stripe.PaymentIntent.retrieve(payment_id)
                return True, {
                    "status": intent.status,
                    "amount": intent.amount / 100,
                    "currency": intent.currency,
                    "created": datetime.fromtimestamp(intent.created)
                }
            
            elif provider == PaymentProvider.PAYPAL:
                payment = paypalrestsdk.Payment.find(payment_id)
                if payment.state == "approved":
                    return True, {
                        "status": payment.state,
                        "amount": float(payment.transactions[0].amount.total),
                        "currency": payment.transactions[0].amount.currency,
                        "created": datetime.strptime(payment.create_time, "%Y-%m-%dT%H:%M:%SZ")
                    }
                return False, {"error": payment.failure_reason}
            
            return False, {"error": "Invalid payment provider"}
        except Exception as e:
            return False, {"error": str(e)}

    async def detect_fraud(
        self,
        payment_data: Dict,
        provider: PaymentProvider
    ) -> Tuple[bool, Dict]:
        """Basic fraud detection"""
        try:
            if provider == PaymentProvider.STRIPE:
                # Use Stripe Radar for fraud detection
                charge = stripe.Charge.retrieve(payment_data.get("charge_id"))
                if charge.outcome.get("risk_level") == "elevated":
                    return False, {"fraud": True, "reason": charge.outcome.get("reason")}
                return True, {"fraud": False}
            
            elif provider == PaymentProvider.PAYPAL:
                # Use PayPal's fraud filters
                payment = paypalrestsdk.Payment.find(payment_data.get("payment_id"))
                if payment.fmf_details and payment.fmf_details.filter_type == "Deny":
                    return False, {"fraud": True, "reason": payment.fmf_details.filter_id}
                return True, {"fraud": False}
            
            return False, {"error": "Invalid payment provider"}
        except Exception as e:
            return False, {"error": str(e)}
