import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
from core.database import query_db

# Configure logging
logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self, api_key: str, webhook_secret: str):
        stripe.api_key = api_key
        self.webhook_secret = webhook_secret
        self.retry_attempts = 3

    async def handle_webhook(self, payload: str, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook event with validation."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
        except ValueError as e:
            logger.error(f"Invalid Stripe payload: {str(e)}")
            return {"success": False, "error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid Stripe signature: {str(e)}")
            return {"success": False, "error": "Invalid signature"}

        # Process different event types
        if event["type"] == "payment_intent.succeeded":
            return await self._handle_payment_success(event["data"]["object"])
        elif event["type"] == "payment_intent.payment_failed":
            return await self._handle_payment_failure(event["data"]["object"])
        else:
            logger.info(f"Unhandled Stripe event type: {event['type']}")
            return {"success": True, "message": "Event not processed"}

    async def _handle_payment_success(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Process successful payment and trigger fulfillment."""
        amount_cents = payment_intent["amount"]
        metadata = payment_intent.get("metadata", {})
        customer_email = payment_intent.get("charges", {}).get("data", [{}])[0].get("billing_details", {}).get("email", "")

        # Record revenue event
        revenue_data = {
            "event_type": "revenue",
            "amount_cents": amount_cents,
            "currency": payment_intent["currency"],
            "source": "stripe",
            "metadata": {
                "payment_intent_id": payment_intent["id"],
                "customer_email": customer_email,
                **metadata
            }
        }

        # Retry logic for database operations
        for attempt in range(self.retry_attempts):
            try:
                await self._record_revenue_event(revenue_data)
                break
            except Exception as e:
                if attempt == self.retry_attempts - 1:
                    logger.error(f"Failed to record revenue after {self.retry_attempts} attempts: {str(e)}")
                    return {"success": False, "error": "Failed to record revenue"}

        # Trigger fulfillment
        fulfillment_result = await self._trigger_fulfillment(payment_intent)
        if not fulfillment_result.get("success"):
            logger.error(f"Fulfillment failed: {fulfillment_result.get('error')}")

        return {"success": True, "message": "Payment processed"}

    async def _handle_payment_failure(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment attempts."""
        logger.warning(f"Payment failed: {payment_intent['last_payment_error']}")
        return {"success": True, "message": "Payment failure logged"}

    async def _record_revenue_event(self, data: Dict[str, Any]) -> None:
        """Record revenue event in database."""
        sql = f"""
        INSERT INTO revenue_events (
            id, event_type, amount_cents, currency, source, 
            metadata, recorded_at, created_at
        ) VALUES (
            gen_random_uuid(),
            '{data['event_type']}',
            {data['amount_cents']},
            '{data['currency']}',
            '{data['source']}',
            '{json.dumps(data.get('metadata', {}))}'::jsonb,
            NOW(),
            NOW()
        )
        """
        await query_db(sql)

    async def _trigger_fulfillment(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger product/service fulfillment based on payment."""
        # Extract product/service details from metadata
        product_id = payment_intent.get("metadata", {}).get("product_id")
        
        if not product_id:
            return {"success": False, "error": "No product ID in metadata"}
            
        try:
            # TODO: Implement actual fulfillment logic
            # This could be:
            # - Digital product delivery
            # - Service scheduling 
            # - Physical product shipping
            logger.info(f"Fulfillment triggered for product {product_id}")
            return {"success": True, "message": "Fulfillment initiated"}
        except Exception as e:
            logger.error(f"Fulfillment error: {str(e)}")
            return {"success": False, "error": str(e)}
