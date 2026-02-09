import stripe
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self, api_key: str, webhook_secret: str):
        stripe.api_key = api_key
        self.webhook_secret = webhook_secret
        self.currency = "usd"

    async def create_payment_intent(
        self,
        amount_cents: int,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a Stripe PaymentIntent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=self.currency,
                customer=customer_id,
                metadata=metadata or {},
                payment_method_types=["card"],
                capture_method="automatic"
            )
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id
            }
        except Exception as e:
            logger.error(f"Failed to create payment intent: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_webhook_event(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process incoming Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            event_handler = {
                "payment_intent.succeeded": self._handle_payment_succeeded,
                "payment_intent.payment_failed": self._handle_payment_failed,
                "invoice.paid": self._handle_invoice_paid,
            }.get(event.type, lambda e: None)
            
            await event_handler(event)
            return {"success": True}

        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _handle_payment_succeeded(self, event) -> None:
        """Handle successful payment."""
        intent = event.data.object
        logger.info(f"Payment succeeded: {intent.id}")
        # TODO: Trigger fulfillment

    async def _handle_payment_failed(self, event) -> None:
        """Handle failed payment."""
        intent = event.data.object
        logger.warning(f"Payment failed: {intent.id}")
        # TODO: Notify user

    async def _handle_invoice_paid(self, event) -> None:
        """Handle subscription invoice paid."""
        invoice = event.data.object
        logger.info(f"Invoice paid: {invoice.id}")
        # TODO: Handle subscription renewal
