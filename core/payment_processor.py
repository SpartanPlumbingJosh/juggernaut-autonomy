import os
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from enum import Enum, auto
import json
import logging

logger = logging.getLogger(__name__)

class PaymentProvider(Enum):
    STRIPE = auto()
    PAYPAL = auto()

class PaymentProcessor:
    def __init__(self):
        # Initialize payment providers
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
        metadata: Optional[Dict] = None,
        customer_email: Optional[str] = None,
        description: Optional[str] = None,
        retries: int = 3
    ) -> Tuple[Optional[str], Optional[str]]:
        """Create payment intent with retry logic."""
        metadata = metadata or {}
        for attempt in range(retries):
            try:
                if provider == PaymentProvider.STRIPE:
                    intent = stripe.PaymentIntent.create(
                        amount=int(amount * 100),  # Convert to cents
                        currency=currency.lower(),
                        metadata=metadata,
                        receipt_email=customer_email,
                        description=description
                    )
                    return intent.id, intent.client_secret
                
                elif provider == PaymentProvider.PAYPAL:
                    payment = paypalrestsdk.Payment({
                        "intent": "sale",
                        "payer": {"payment_method": "paypal"},
                        "transactions": [{
                            "amount": {
                                "total": f"{amount:.2f}",
                                "currency": currency.upper()
                            },
                            "description": description
                        }],
                        "redirect_urls": {
                            "return_url": os.getenv("PAYPAL_RETURN_URL"),
                            "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                        }
                    })
                    if payment.create():
                        return payment.id, payment.links[1].href
                    raise Exception(payment.error)
                
            except Exception as e:
                logger.error(f"Payment attempt {attempt + 1} failed: {str(e)}")
                if attempt == retries - 1:
                    return None, None
                
        return None, None

    async def confirm_payment(
        self,
        payment_id: str,
        provider: PaymentProvider,
        payer_id: Optional[str] = None
    ) -> bool:
        """Confirm payment completion."""
        try:
            if provider == PaymentProvider.STRIPE:
                intent = stripe.PaymentIntent.retrieve(payment_id)
                return intent.status == "succeeded"
            
            elif provider == PaymentProvider.PAYPAL:
                payment = paypalrestsdk.Payment.find(payment_id)
                if payer_id:
                    return payment.execute({"payer_id": payer_id})
                return payment.state == "approved"
                
        except Exception as e:
            logger.error(f"Payment confirmation failed: {str(e)}")
            return False

    async def generate_receipt(
        self,
        payment_id: str,
        provider: PaymentProvider,
        amount: float,
        currency: str,
        customer_email: str,
        metadata: Optional[Dict] = None
    ) -> Optional[str]:
        """Generate payment receipt."""
        try:
            receipt_data = {
                "payment_id": payment_id,
                "provider": provider.name,
                "amount": amount,
                "currency": currency,
                "customer_email": customer_email,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": metadata or {}
            }
            return json.dumps(receipt_data)
        except Exception as e:
            logger.error(f"Receipt generation failed: {str(e)}")
            return None

    async def handle_payment_webhook(
        self,
        payload: Dict,
        provider: PaymentProvider,
        signature: Optional[str] = None
    ) -> bool:
        """Handle payment webhook events."""
        try:
            if provider == PaymentProvider.STRIPE:
                event = stripe.Webhook.construct_event(
                    payload,
                    signature,
                    os.getenv("STRIPE_WEBHOOK_SECRET")
                )
                return self._process_stripe_event(event)
            
            elif provider == PaymentProvider.PAYPAL:
                return self._process_paypal_event(payload)
                
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return False

    def _process_stripe_event(self, event: Dict) -> bool:
        """Process Stripe webhook event."""
        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})
        
        if event_type == "payment_intent.succeeded":
            return self._handle_successful_payment(
                provider=PaymentProvider.STRIPE,
                payment_id=data.get("id"),
                amount=data.get("amount") / 100,
                currency=data.get("currency"),
                customer_email=data.get("receipt_email"),
                metadata=data.get("metadata")
            )
            
        return False

    def _process_paypal_event(self, event: Dict) -> bool:
        """Process PayPal webhook event."""
        event_type = event.get("event_type")
        resource = event.get("resource", {})
        
        if event_type == "PAYMENT.SALE.COMPLETED":
            return self._handle_successful_payment(
                provider=PaymentProvider.PAYPAL,
                payment_id=resource.get("id"),
                amount=float(resource.get("amount", {}).get("total", 0)),
                currency=resource.get("amount", {}).get("currency"),
                customer_email=resource.get("payer", {}).get("payer_info", {}).get("email"),
                metadata=resource.get("metadata", {})
            )
            
        return False

    def _handle_successful_payment(
        self,
        provider: PaymentProvider,
        payment_id: str,
        amount: float,
        currency: str,
        customer_email: str,
        metadata: Dict
    ) -> bool:
        """Handle successful payment."""
        # TODO: Implement product delivery and customer onboarding
        # This should trigger the fulfillment pipeline
        return True
