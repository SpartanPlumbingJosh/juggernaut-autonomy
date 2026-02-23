"""
Payment Processor - Handles Stripe integration and payment processing.

Features:
- Create payment intents
- Handle webhooks
- Process refunds
- Track payment status
"""

import os
import stripe
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Payment limits for safety
MAX_PAYMENT_AMOUNT = 10000  # $100.00
DAILY_PAYMENT_LIMIT = 100000  # $1000.00
MIN_PAYMENT_AMOUNT = 50  # $0.50

class PaymentProcessor:
    def __init__(self):
        self.currency = "usd"
        
    async def create_payment_intent(self, amount: int, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe payment intent with safety checks."""
        try:
            # Validate amount
            if amount < MIN_PAYMENT_AMOUNT:
                return {"error": f"Amount must be at least {MIN_PAYMENT_AMOUNT} cents"}
                
            if amount > MAX_PAYMENT_AMOUNT:
                return {"error": f"Amount exceeds maximum of {MAX_PAYMENT_AMOUNT} cents"}
                
            # Check daily limit
            today = datetime.now(timezone.utc).date()
            daily_total = await self._get_daily_total(today)
            if daily_total + amount > DAILY_PAYMENT_LIMIT:
                return {"error": "Daily payment limit exceeded"}
                
            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=self.currency,
                metadata=metadata,
                capture_method="automatic"
            )
            
            # Log payment creation
            await self._log_payment_event(intent.id, "payment_intent.created", intent)
            
            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "status": intent.status
            }
            
        except stripe.error.StripeError as e:
            return {"error": str(e)}
            
    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
            
            # Handle specific event types
            if event.type == "payment_intent.succeeded":
                await self._handle_payment_success(event.data.object)
            elif event.type == "payment_intent.payment_failed":
                await self._handle_payment_failure(event.data.object)
                
            return {"success": True}
            
        except stripe.error.SignatureVerificationError as e:
            return {"error": "Invalid signature"}
        except Exception as e:
            return {"error": str(e)}
            
    async def _handle_payment_success(self, payment_intent) -> None:
        """Handle successful payment."""
        await self._log_payment_event(
            payment_intent.id,
            "payment_intent.succeeded",
            payment_intent
        )
        
        # Trigger service delivery
        await self._deliver_service(payment_intent)
        
    async def _handle_payment_failure(self, payment_intent) -> None:
        """Handle failed payment."""
        await self._log_payment_event(
            payment_intent.id,
            "payment_intent.failed",
            payment_intent
        )
        
    async def _deliver_service(self, payment_intent) -> None:
        """Deliver service after successful payment."""
        try:
            # Extract metadata
            metadata = payment_intent.metadata
            service_type = metadata.get("service_type")
            
            # Implement service delivery logic
            if service_type == "digital_product":
                await self._deliver_digital_product(metadata)
            elif service_type == "subscription":
                await self._start_subscription(metadata)
                
        except Exception as e:
            await self._log_payment_event(
                payment_intent.id,
                "service_delivery.failed",
                {"error": str(e)}
            )
            
    async def _deliver_digital_product(self, metadata: Dict[str, Any]) -> None:
        """Deliver digital product."""
        # Implementation would include:
        # - Generate download link
        # - Send email with access instructions
        # - Update user account
        pass
        
    async def _start_subscription(self, metadata: Dict[str, Any]) -> None:
        """Start subscription service."""
        # Implementation would include:
        # - Create subscription record
        # - Set up recurring billing
        # - Grant access to subscription features
        pass
        
    async def _log_payment_event(self, payment_id: str, event_type: str, data: Dict[str, Any]) -> None:
        """Log payment event to database."""
        try:
            await query_db(f"""
                INSERT INTO payment_events (
                    payment_id, event_type, data, created_at
                ) VALUES (
                    '{payment_id}',
                    '{event_type}',
                    '{json.dumps(data)}',
                    NOW()
                )
            """)
        except Exception as e:
            # Fallback logging if database fails
            print(f"Failed to log payment event: {str(e)}")
            
    async def _get_daily_total(self, date) -> int:
        """Get total payments for the day."""
        try:
            result = await query_db(f"""
                SELECT SUM(amount) as total
                FROM payment_events
                WHERE event_type = 'payment_intent.succeeded'
                AND created_at::date = '{date.isoformat()}'
            """)
            return int(result.get("rows", [{}])[0].get("total", 0))
        except Exception:
            return 0
            
    async def process_refund(self, payment_id: str, amount: int) -> Dict[str, Any]:
        """Process refund for a payment."""
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_id,
                amount=amount
            )
            
            await self._log_payment_event(
                payment_id,
                "refund.created",
                {"amount": amount, "refund_id": refund.id}
            )
            
            return {"success": True, "refund_id": refund.id}
            
        except stripe.error.StripeError as e:
            return {"error": str(e)}
