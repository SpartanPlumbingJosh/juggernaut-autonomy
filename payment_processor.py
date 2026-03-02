import os
import uuid
import logging
from typing import Dict, Optional, Tuple
from enum import Enum

import stripe
import paypalrestsdk

class PaymentProvider(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"

class PaymentProcessor:
    def __init__(self):
        self.stripe_api_key = os.getenv("STRIPE_API_KEY")
        self.paypal_client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.paypal_secret = os.getenv("PAYPAL_SECRET")
        
        stripe.api_key = self.stripe_api_key
        paypalrestsdk.configure({
            "mode": "live",
            "client_id": self.paypal_client_id,
            "client_secret": self.paypal_secret
        })
        
        self.logger = logging.getLogger(__name__)

    async def create_payment(self, 
                           amount: float,
                           currency: str,
                           provider: PaymentProvider,
                           metadata: Dict,
                           user_id: str) -> Tuple[str, Optional[Dict]]:
        """
        Create a payment intent and return payment URL.
        Args:
            amount: Payment amount
            currency: 3-letter currency code
            provider: Payment provider enum
            metadata: Additional payment metadata
            user_id: User ID making payment
        Returns:
            (payment_id:string, payment_data:dict)
        """
        payment_id = str(uuid.uuid4())
        
        try:
            if provider == PaymentProvider.STRIPE:
                intent = stripe.PaymentIntent.create(
                    amount=int(amount * 100),  # stripe uses cents
                    currency=currency.lower(),
                    metadata={
                        **metadata,
                        "user_id": user_id,
                        "payment_id": payment_id
                    }
                )
                return payment_id, {"client_secret": intent.client_secret}
                
            elif provider == PaymentProvider.PAYPAL:
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": str(amount),
                            "currency": currency.upper()
                        },
                        "description": "Purchase",
                        "custom": user_id,
                        "invoice_number": payment_id,
                        "item_list": {"items": metadata.get("items", [])}
                    }],
                    "redirect_urls": {
                        "return_url": os.getenv("PAYPAL_RETURN_URL"),
                        "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                    }
                })
                
                if payment.create():
                    return payment_id, {
                        "approval_url": next(
                            link.href for link in payment.links 
                            if link.method == "REDIRECT"
                        )
                    }
                else:
                    raise Exception(payment.error)
                    
        except Exception as e:
            self.logger.error(f"Payment creation failed: {str(e)}")
            raise

    def verify_webhook(self, payload: bytes, signature: str, provider: PaymentProvider) -> bool:
        """Verify webhook signature"""
        if provider == PaymentProvider.STRIPE:
            try:
                event = stripe.Webhook.construct_event(
                    payload, 
                    signature, 
                    os.getenv("STRIPE_WEBHOOK_SECRET")
                )
                return True
            except Exception:
                return False
        elif provider == PaymentProvider.PAYPAL:
            # Paypal verification requires different approach
            return True  # TODO: Implement actual verification
            
        return False
