"""
Payment processing system with Stripe/PayPal integration.
Handles subscriptions, one-time payments, and billing events.
"""
import os
import stripe
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self):
        self.stripe = stripe

    async def create_customer(self, email: str, name: str) -> Dict:
        """Create a new customer in Stripe."""
        try:
            customer = self.stripe.Customer.create(
                email=email,
                name=name,
                metadata={
                    "created_at": datetime.utcnow().isoformat()
                }
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_subscription(
        self, 
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create a subscription for a customer."""
        try:
            subscription = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"],
                metadata=metadata or {}
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret
            }
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Tuple[int, Dict]:
        """Process Stripe webhook events."""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
            
            event_type = event['type']
            data = event['data']['object']
            
            if event_type == 'payment_intent.succeeded':
                await self._handle_payment_success(data)
            elif event_type == 'invoice.paid':
                await self._handle_invoice_paid(data)
            elif event_type == 'invoice.payment_failed':
                await self._handle_payment_failed(data)
            
            return 200, {"status": "success"}
        except ValueError as e:
            return 400, {"error": str(e)}
        except self.stripe.error.SignatureVerificationError as e:
            return 400, {"error": "Invalid signature"}
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return 500, {"error": "Internal server error"}

    async def _handle_payment_success(self, payment_intent: Dict) -> None:
        """Handle successful payment."""
        # TODO: Implement service delivery
        logger.info(f"Payment succeeded: {payment_intent['id']}")

    async def _handle_invoice_paid(self, invoice: Dict) -> None:
        """Handle paid invoice (subscription renewal)."""
        # TODO: Implement subscription renewal logic
        logger.info(f"Invoice paid: {invoice['id']}")

    async def _handle_payment_failed(self, invoice: Dict) -> None:
        """Handle failed payment."""
        # TODO: Implement retry/dunning logic
        logger.warning(f"Payment failed: {invoice['id']}")

    async def cancel_subscription(self, subscription_id: str) -> Dict:
        """Cancel a subscription."""
        try:
            sub = self.stripe.Subscription.delete(subscription_id)
            return {"success": True, "status": sub.status}
        except Exception as e:
            logger.error(f"Failed to cancel subscription: {str(e)}")
            return {"success": False, "error": str(e)}
