import stripe
import json
from datetime import datetime
from typing import Dict, Any, Optional
from core.database import query_db

class StripeProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.webhook_secret = None

    async def create_checkout_session(self, price_id: str, customer_email: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe checkout session"""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='payment',
                customer_email=customer_email,
                metadata=metadata,
                success_url=f"https://yourdomain.com/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"https://yourdomain.com/cancel",
            )
            return {"success": True, "session_id": session.id, "url": session.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Handle Stripe webhook events"""
        if not self.webhook_secret:
            return {"success": False, "error": "Webhook secret not configured"}

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
        except ValueError as e:
            return {"success": False, "error": f"Invalid payload: {str(e)}"}
        except stripe.error.SignatureVerificationError as e:
            return {"success": False, "error": f"Invalid signature: {str(e)}"}

        # Handle the event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            await self._handle_payment_success(session)

        return {"success": True}

    async def _handle_payment_success(self, session: Dict[str, Any]) -> None:
        """Process successful payment"""
        metadata = session.get('metadata', {})
        amount_total = session.get('amount_total', 0)  # in cents
        customer_email = session.get('customer_email', '')

        # Record the transaction
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_total},
                'usd',
                'stripe',
                '{json.dumps(metadata)}',
                NOW(),
                NOW()
            )
        """)

        # Trigger delivery pipeline
        await self._trigger_delivery_pipeline(metadata)

    async def _trigger_delivery_pipeline(self, metadata: Dict[str, Any]) -> None:
        """Trigger automated service delivery"""
        # Implement your delivery logic here
        # This could include:
        # - Generating/downloading files
        # - Sending emails
        # - Activating accounts
        # - Calling external APIs
        pass
