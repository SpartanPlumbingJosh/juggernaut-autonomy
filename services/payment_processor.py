import os
import logging
import stripe
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.database import query_db

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

class PaymentProcessor:
    @staticmethod
    async def handle_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(f"Invalid payload: {str(e)}")
            return {"error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {str(e)}")
            return {"error": "Invalid signature"}

        # Handle specific event types
        if event["type"] == "payment_intent.succeeded":
            return await PaymentProcessor._handle_payment_success(event["data"]["object"])
        elif event["type"] == "payment_intent.payment_failed":
            return await PaymentProcessor._handle_payment_failure(event["data"]["object"])
        
        logger.info(f"Unhandled event type: {event['type']}")
        return {"status": "unhandled_event"}

    @staticmethod
    async def _handle_payment_success(payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment."""
        try:
            # Record transaction
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, 
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {payment_intent["amount"]},
                    '{payment_intent["currency"]}',
                    'stripe',
                    '{json.dumps(payment_intent)}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            
            # Deliver service
            await PaymentProcessor._deliver_service(payment_intent)
            
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to process payment: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    async def _handle_payment_failure(payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment with retry logic."""
        logger.warning(f"Payment failed: {payment_intent['id']}")
        
        try:
            # Record failed payment
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, 
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'payment_failed',
                    {payment_intent["amount"]},
                    '{payment_intent["currency"]}',
                    'stripe',
                    '{json.dumps(payment_intent)}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            
            # Attempt retry if appropriate
            if payment_intent.get("next_action") and payment_intent.get("next_action")["type"] == "redirect_to_url":
                return {"status": "requires_action", "next_action": payment_intent["next_action"]}
                
            return {"status": "failed"}
        except Exception as e:
            logger.error(f"Failed to record failed payment: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    async def _deliver_service(payment_intent: Dict[str, Any]) -> None:
        """Deliver the purchased service."""
        # TODO: Implement actual service delivery logic
        logger.info(f"Delivering service for payment {payment_intent['id']}")
        return

    @staticmethod
    async def create_payment_intent(amount: float, currency: str = "usd") -> Dict[str, Any]:
        """Create a new payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency,
                automatic_payment_methods={"enabled": True},
            )
            return {"client_secret": intent["client_secret"]}
        except Exception as e:
            logger.error(f"Failed to create payment intent: {str(e)}")
            return {"error": str(e)}
