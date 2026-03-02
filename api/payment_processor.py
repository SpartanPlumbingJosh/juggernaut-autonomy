"""
Payment processing integration for Stripe and PayPal.
Handles payment creation, verification, and webhooks.
"""

import json
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from core.database import query_db
from api.revenue_api import _make_response, _error_response


class PaymentProcessor:
    def __init__(self):
        # Initialize payment providers
        stripe.api_key = "sk_test_"  # Should be from env vars
        paypalrestsdk.configure({
            "mode": "sandbox",  # production/sandbox
            "client_id": "client-id-from-env",
            "client_secret": "client-secret-from-env"
        })

    async def create_payment_intent(
        self,
        amount_cents: int,
        currency: str = "usd",
        metadata: Optional[Dict[str, Any]] = None,
        payment_method: str = "stripe"
    ) -> Dict[str, Any]:
        """Create a new payment intent with Stripe/PayPal."""
        try:
            metadata = metadata or {}
            
            # Common fields for revenue tracking
            metadata.update({
                "system_source": "payment_processor",
                "processed_at": datetime.now(timezone.utc).isoformat()
            })

            if payment_method == "stripe":
                intent = stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=currency,
                    metadata=metadata,
                    capture_method="automatic"
                )
                return {
                    "success": True,
                    "payment_id": intent.id,
                    "client_secret": intent.client_secret,
                    "amount_cents": amount_cents,
                    "currency": currency,
                    "requires_action": intent.status == "requires_action",
                    "payment_method": "stripe"
                }

            elif payment_method == "paypal":
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": f"{amount_cents / 100:.2f}",
                            "currency": currency.upper()
                        }
                    }],
                    "redirect_urls": {
                        "return_url": "https://example.com/success",
                        "cancel_url": "https://example.com/cancel"
                    }
                })
                if payment.create():
                    return {
                        "success": True,
                        "payment_id": payment.id,
                        "approval_url": next(
                            link.href for link in payment.links 
                            if link.method == "REDIRECT"
                        ),
                        "amount_cents": amount_cents,
                        "currency": currency,
                        "payment_method": "paypal"
                    }

            return _error_response(400, "Unsupported payment method")

        except Exception as e:
            return _error_response(500, f"Payment creation failed: {str(e)}")

    async def handle_payment_webhook(
        self,
        payload: Dict[str, Any],
        sig_header: Optional[str] = None,
        source: str = "stripe"
    ) -> Dict[str, Any]:
        """Process payment webhooks from Stripe/PayPal."""
        try:
            event = None
            if source == "stripe":
                event = stripe.Webhook.construct_event(
                    json.dumps(payload),
                    sig_header if sig_header else "",
                    "webhook-secret-from-env"  # Should be from env vars
                )
            elif source == "paypal":
                event = payload  # PayPal verifies via IPN
            
            if not event:
                return _error_response(400, "Invalid webhook source")

            # Handle payment success
            if (source == "stripe" and event["type"] == "payment_intent.succeeded") or \
               (source == "paypal" and event["event_type"] == "PAYMENT.SALE.COMPLETED"):
                
                payment_id = event.data.object.id if source == "stripe" else event.resource.sale_id
                amount_cents = event.data.object.amount if source == "stripe" else int(float(event.resource.amount.total) * 100)
                
                # Record payment in revenue events
                sql = f"""
                INSERT INTO revenue_events (
                    id, experiment_id, event_type, amount_cents, 
                    currency, source, metadata, recorded_at, created_at
                ) VALUES (
                    uuid_generate_v4(), NULL, 'revenue', {amount_cents},
                    '{event.data.object.currency if source == "stripe' else event.resource.amount.currency}', 
                    'payment_processor', 
                    '{{"payment_id": "{payment_id}", "source": "{source}"}}'::jsonb,
                    NOW(), NOW()
                )
                """
                await query_db(sql)
                
                # Trigger delivery
                await self._fulfill_order(event.data.object.metadata if source == "stripe" else event.resource.custom)
                
                return _make_response(200, {"status": "processed"})

            return _make_response(200, {"status": "ignored"})

        except Exception as e:
            return _error_response(500, f"Webhook processing failed: {str(e)}")

    async def _fulfill_order(self, order_details: Dict[str, Any]) -> None:
        """Handle order fulfillment based on payment metadata."""
        # Implement product/service specific delivery logic
        # Could be:
        # - Send digital product email
        # - Trigger API call to fulfillment service
        # - Update database with access permissions
        # - Queue background task
        pass
