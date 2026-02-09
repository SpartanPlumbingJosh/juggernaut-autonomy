import os
import stripe
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import HTTPException

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class PaymentProcessor:
    """Handle payment processing across multiple gateways"""
    
    def __init__(self):
        self.gateways = {
            "stripe": self._process_stripe_payment
        }
    
    async def process_payment(self, gateway: str, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through specified gateway"""
        processor = self.gateways.get(gateway.lower())
        if not processor:
            raise HTTPException(status_code=400, detail="Unsupported payment gateway")
        
        try:
            return await processor(payment_data)
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    async def _process_stripe_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through Stripe"""
        intent = stripe.PaymentIntent.create(
            amount=int(payment_data["amount"] * 100),  # Convert to cents
            currency=payment_data.get("currency", "usd"),
            payment_method=payment_data["payment_method_id"],
            confirmation_method="manual",
            confirm=True,
            metadata=payment_data.get("metadata", {})
        )
        
        return {
            "payment_id": intent.id,
            "status": intent.status,
            "amount": intent.amount / 100,
            "currency": intent.currency,
            "created": datetime.utcfromtimestamp(intent.created).isoformat()
        }

    async def handle_webhook(self, gateway: str, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process webhook events"""
        if gateway.lower() == "stripe":
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
                )
                
                # Handle specific event types
                if event.type == "payment_intent.succeeded":
                    return await self._handle_payment_success(event.data.object)
                elif event.type == "payment_intent.payment_failed":
                    return await self._handle_payment_failure(event.data.object)
                
            except stripe.error.SignatureVerificationError as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        return {"status": "unhandled_event"}
    
    async def _handle_payment_success(self, payment_intent) -> Dict[str, Any]:
        """Handle successful payment"""
        # TODO: Trigger provisioning and record transaction
        return {
            "event": "payment_success",
            "payment_id": payment_intent.id,
            "amount": payment_intent.amount / 100,
            "currency": payment_intent.currency
        }
    
    async def _handle_payment_failure(self, payment_intent) -> Dict[str, Any]:
        """Handle failed payment"""
        # TODO: Trigger dunning process
        return {
            "event": "payment_failure",
            "payment_id": payment_intent.id,
            "error": payment_intent.last_payment_error
        }
