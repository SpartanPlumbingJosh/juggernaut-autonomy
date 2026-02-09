import logging
import stripe
from typing import Dict, Any
from datetime import datetime
from config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Handle Stripe payment operations."""
    
    @staticmethod
    def create_customer(email: str, name: str) -> Dict[str, Any]:
        """Create Stripe customer."""
        try:
            return stripe.Customer.create(
                email=email,
                name=name,
                metadata={
                    "created_at": datetime.utcnow().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            raise

    @staticmethod
    def create_subscription(customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create Stripe subscription."""
        try:
            return stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"],
            )
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            raise

    @staticmethod
    def handle_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            
            if event["type"] == "payment_intent.succeeded":
                return {"success": True, "event": "payment_processed"}
                
            return {"success": False, "error": "Unhandled event type"}
            
        except ValueError as e:
            logger.error(f"Invalid payload: {str(e)}")
            raise
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {str(e)}")
            raise
