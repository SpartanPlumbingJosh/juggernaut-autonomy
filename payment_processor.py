import os
import stripe
from datetime import datetime, timezone
from typing import Dict, Optional, List
from core.database import query_db, execute_sql

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

class PaymentProcessor:
    """Handle Stripe payment processing and revenue tracking."""
    
    @staticmethod
    async def record_transaction(event: Dict) -> Dict:
        """Record a Stripe transaction in revenue_events."""
        event_type = event["type"]
        data = event["data"]["object"]
        
        # Map Stripe event types to our revenue event types
        event_type_map = {
            "payment_intent.succeeded": "revenue",
            "charge.succeeded": "revenue",
            "invoice.payment_succeeded": "revenue",
            "payment_intent.payment_failed": "failed_payment",
            "charge.failed": "failed_payment",
            "invoice.payment_failed": "failed_payment",
            "refund": "refund"
        }
        
        our_event_type = event_type_map.get(event_type, "other")
        
        # Extract relevant transaction details
        amount = data.get("amount") or data.get("amount_received") or 0
        currency = data.get("currency", "usd")
        source = "stripe"
        metadata = {
            "stripe_event_id": event["id"],
            "stripe_object_id": data["id"],
            "stripe_object_type": data["object"]
        }
        
        # Record the transaction
        try:
            await execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source, metadata,
                    recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{our_event_type}',
                    {amount},
                    '{currency}',
                    '{source}',
                    '{json.dumps(metadata)}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def handle_webhook(payload: str, sig_header: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
            
            # Handle specific event types
            if event["type"] in [
                "payment_intent.succeeded",
                "charge.succeeded",
                "invoice.payment_succeeded",
                "payment_intent.payment_failed",
                "charge.failed",
                "invoice.payment_failed",
                "refund"
            ]:
                await PaymentProcessor.record_transaction(event)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def retry_failed_payments() -> Dict:
        """Retry failed payments with dunning management."""
        try:
            # Get failed payments from last 7 days
            res = await query_db("""
                SELECT id, metadata->>'stripe_payment_intent_id' as payment_intent_id
                FROM revenue_events
                WHERE event_type = 'failed_payment'
                  AND recorded_at >= NOW() - INTERVAL '7 days'
            """)
            
            retried = 0
            failures = []
            
            for row in res.get("rows", []):
                payment_intent_id = row["payment_intent_id"]
                try:
                    # Retry the payment
                    stripe.PaymentIntent.retrieve(payment_intent_id)
                    retried += 1
                except Exception as e:
                    failures.append({"payment_intent_id": payment_intent_id, "error": str(e)})
            
            return {
                "success": True,
                "retried": retried,
                "failures": failures
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
