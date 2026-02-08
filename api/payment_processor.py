"""
Payment Processor - Handles payment integrations with Stripe/PayPal.

Features:
- Payment intent creation
- Webhook handling
- Receipt generation
- Transaction logging
"""

import os
import json
import stripe
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from core.database import query_db

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Handles payment processing and transaction logging."""
    
    def __init__(self):
        self.currency = "usd"
        
    async def create_payment_intent(self, amount_cents: int, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=self.currency,
                metadata=metadata,
                automatic_payment_methods={"enabled": True},
            )
            
            # Log the payment intent
            await self._log_transaction(
                event_type="payment_intent",
                amount_cents=amount_cents,
                metadata={
                    "payment_intent_id": intent.id,
                    "client_secret": intent.client_secret,
                    **metadata
                }
            )
            
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Payment intent creation failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def handle_webhook(self, payload: str, sig_header: str) -> Dict[str, Any]:
        """Handle Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
            )
            
            if event.type == "payment_intent.succeeded":
                payment_intent = event.data.object
                await self._log_transaction(
                    event_type="revenue",
                    amount_cents=payment_intent.amount,
                    metadata={
                        "payment_intent_id": payment_intent.id,
                        "currency": payment_intent.currency,
                        "customer": payment_intent.customer,
                        "payment_method": payment_intent.payment_method
                    }
                )
                
                # TODO: Trigger delivery pipeline
                
            return {"success": True}
            
        except stripe.error.StripeError as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def _log_transaction(self, event_type: str, amount_cents: int, metadata: Dict[str, Any]) -> None:
        """Log transaction to revenue_events table."""
        try:
            await query_db(f"""
                INSERT INTO revenue_events (
                    id,
                    event_type,
                    amount_cents,
                    currency,
                    source,
                    metadata,
                    recorded_at,
                    created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{event_type}',
                    {amount_cents},
                    '{self.currency}',
                    'stripe',
                    '{json.dumps(metadata)}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
        except Exception as e:
            logger.error(f"Failed to log transaction: {str(e)}")
            
    async def generate_receipt(self, payment_intent_id: str) -> Dict[str, Any]:
        """Generate a receipt for a completed payment."""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            receipt = {
                "id": intent.id,
                "amount": intent.amount / 100,
                "currency": intent.currency,
                "status": intent.status,
                "created": datetime.fromtimestamp(intent.created, tz=timezone.utc).isoformat(),
                "customer": intent.customer,
                "payment_method": intent.payment_method,
                "metadata": intent.metadata
            }
            
            return {
                "success": True,
                "receipt": receipt
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Receipt generation failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

# Initialize singleton instance
payment_processor = PaymentProcessor()
