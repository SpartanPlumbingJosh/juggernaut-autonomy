import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
import paypalrestsdk

from core.database import execute_sql
from core.alerting import send_alert

# Configure payment processors
stripe.api_key = "sk_test_..."  # Should be from env vars
paypalrestsdk.configure({
    "mode": "sandbox",  # or "live"
    "client_id": "...",
    "client_secret": "..."
})

class PaymentProcessor:
    """Handle payment processing and webhooks for multiple providers."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.retry_attempts = 3
        
    async def handle_stripe_webhook(self, payload: Dict[str, Any], sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                json.dumps(payload), 
                sig_header, 
                stripe.webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                return await self._process_payment(event['data']['object'])
            elif event['type'] == 'charge.refunded':
                return await self._process_refund(event['data']['object'])
                
        except Exception as e:
            self.logger.error(f"Stripe webhook error: {str(e)}")
            send_alert("payment_processing_failed", f"Stripe webhook failed: {str(e)}")
            raise
            
    async def handle_paypal_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process PayPal webhook events."""
        try:
            if payload['event_type'] == 'PAYMENT.CAPTURE.COMPLETED':
                return await self._process_payment(payload['resource'])
            elif payload['event_type'] == 'PAYMENT.CAPTURE.REFUNDED':
                return await self._process_refund(payload['resource'])
                
        except Exception as e:
            self.logger.error(f"PayPal webhook error: {str(e)}")
            send_alert("payment_processing_failed", f"PayPal webhook failed: {str(e)}")
            raise
            
    async def _process_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record a successful payment."""
        for attempt in range(self.retry_attempts):
            try:
                amount_cents = int(float(payment_data['amount']) * 100)
                await execute_sql(
                    f"""
                    INSERT INTO revenue_events (
                        id, event_type, amount_cents, currency, 
                        source, metadata, recorded_at, created_at
                    ) VALUES (
                        gen_random_uuid(), 'revenue', {amount_cents}, 
                        '{payment_data.get('currency', 'usd')}',
                        '{payment_data.get('source', 'unknown')}',
                        '{json.dumps(payment_data)}'::jsonb,
                        NOW(), NOW()
                    )
                    """
                )
                return {"success": True}
            except Exception as e:
                if attempt == self.retry_attempts - 1:
                    send_alert("payment_recording_failed", f"Failed to record payment after {self.retry_attempts} attempts")
                    raise
                continue
                
    async def _process_refund(self, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record a refund."""
        for attempt in range(self.retry_attempts):
            try:
                amount_cents = int(float(refund_data['amount']) * 100)
                await execute_sql(
                    f"""
                    INSERT INTO revenue_events (
                        id, event_type, amount_cents, currency, 
                        source, metadata, recorded_at, created_at
                    ) VALUES (
                        gen_random_uuid(), 'refund', {amount_cents}, 
                        '{refund_data.get('currency', 'usd')}',
                        '{refund_data.get('source', 'unknown')}',
                        '{json.dumps(refund_data)}'::jsonb,
                        NOW(), NOW()
                    )
                    """
                )
                return {"success": True}
            except Exception as e:
                if attempt == self.retry_attempts - 1:
                    send_alert("refund_recording_failed", f"Failed to record refund after {self.retry_attempts} attempts")
                    raise
                continue

    async def create_subscription(self, customer_id: str, plan_id: str) -> Dict[str, Any]:
        """Create recurring subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"plan": plan_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status
            }
        except Exception as e:
            self.logger.error(f"Subscription creation failed: {str(e)}")
            send_alert("subscription_creation_failed", f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}
