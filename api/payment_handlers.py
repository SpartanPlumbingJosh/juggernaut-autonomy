"""
Payment Processing Handlers - Stripe/PayPal integrations and webhooks.
"""
import os
import stripe
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from core.database import query_db
from api.revenue_api import _make_response, _error_response

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_API_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

class PaymentProcessor:
    @staticmethod
    async def create_customer(email: str, name: str) -> Dict[str, Any]:
        """Create a new Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={
                    "registered_at": datetime.now(timezone.utc).isoformat()
                }
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            logging.error(f"Failed to create customer: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def create_subscription(
        customer_id: str,
        price_id: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new Stripe subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                metadata=metadata,
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret
            }
        except Exception as e:
            logging.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def record_charge_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record payment charge in revenue_events table."""
        try:
            await query_db(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, 
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    '{event_data['charge_id']}',
                    'revenue',
                    {int(float(event_data['amount']) * 100)},
                    '{event_data['currency']}',
                    '{event_data['payment_method']}',
                    '{json.dumps(event_data['metadata'])}',
                    '{event_data['timestamp']}',
                    NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            logging.error(f"Failed to record charge: {str(e)}")
            return {"success": False, "error": str(e)}

async def handle_stripe_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """Handle Stripe webhook events."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )

        event_data = event['data']['object']
        event_type = event['type']

        if event_type == 'invoice.paid':
            # Successful payment
            await PaymentProcessor.record_charge_event({
                'charge_id': event_data['charge'],
                'amount': event_data['amount_paid'] / 100,
                'currency': event_data['currency'],
                'payment_method': 'stripe',
                'metadata': event_data['metadata'],
                'timestamp': datetime.fromtimestamp(event_data['created'], timezone.utc).isoformat()
            })

        elif event_type == 'invoice.payment_failed':
            # Failed payment - trigger dunning process
            pass

        elif event_type == 'customer.subscription.deleted':
            # Subscription ended
            pass

        return _make_response(200, {"status": "processed"})

    except ValueError as e:
        return _error_response(400, "Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        return _error_response(400, "Invalid signature")
    except Exception as e:
        logging.error(f"Webhook error: {str(e)}")
        return _error_response(500, "Webhook handler failed")

__all__ = ["PaymentProcessor", "handle_stripe_webhook"]
