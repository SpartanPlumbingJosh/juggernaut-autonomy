from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging
import stripe
import json

logger = logging.getLogger(__name__)

class SubscriptionManager:
    def __init__(self, stripe_api_key: str):
        stripe.api_key = stripe_api_key
        self.webhook_secret = None

    async def create_subscription(
        self,
        customer_email: str,
        plan_id: str,
        payment_method_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            # Create or retrieve customer
            customers = stripe.Customer.list(email=customer_email)
            customer = customers.data[0] if customers.data else stripe.Customer.create(
                email=customer_email,
                payment_method=payment_method_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )

            # Create subscription
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{'price': plan_id}],
                expand=['latest_invoice.payment_intent'],
                metadata=metadata or {}
            )

            # Record subscription event
            await self._record_subscription_event(
                subscription_id=subscription.id,
                customer_id=customer.id,
                event_type='subscription_created',
                metadata={
                    'plan_id': plan_id,
                    'status': subscription.status,
                    'current_period_end': subscription.current_period_end
                }
            )

            return {
                'success': True,
                'subscription_id': subscription.id,
                'status': subscription.status,
                'client_secret': subscription.latest_invoice.payment_intent.client_secret
            }

        except stripe.error.StripeError as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        if not self.webhook_secret:
            return {'success': False, 'error': 'Webhook secret not configured'}

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
        except ValueError as e:
            return {'success': False, 'error': f'Invalid payload: {str(e)}'}
        except stripe.error.SignatureVerificationError as e:
            return {'success': False, 'error': f'Invalid signature: {str(e)}'}

        # Handle specific event types
        event_type = event['type']
        data = event['data']['object']

        if event_type == 'invoice.payment_succeeded':
            await self._handle_payment_success(data)
        elif event_type == 'invoice.payment_failed':
            await self._handle_payment_failure(data)
        elif event_type == 'customer.subscription.deleted':
            await self._handle_subscription_cancellation(data)

        return {'success': True}

    async def _handle_payment_success(self, invoice: Dict[str, Any]) -> None:
        """Process successful payment."""
        subscription_id = invoice['subscription']
        amount_paid = invoice['amount_paid']
        currency = invoice['currency']

        await self._record_subscription_event(
            subscription_id=subscription_id,
            customer_id=invoice['customer'],
            event_type='payment_success',
            metadata={
                'amount_paid': amount_paid,
                'currency': currency,
                'invoice_id': invoice['id']
            }
        )

    async def _handle_payment_failure(self, invoice: Dict[str, Any]) -> None:
        """Process failed payment."""
        subscription_id = invoice['subscription']
        amount_due = invoice['amount_due']
        currency = invoice['currency']

        await self._record_subscription_event(
            subscription_id=subscription_id,
            customer_id=invoice['customer'],
            event_type='payment_failed',
            metadata={
                'amount_due': amount_due,
                'currency': currency,
                'invoice_id': invoice['id']
            }
        )

    async def _handle_subscription_cancellation(self, subscription: Dict[str, Any]) -> None:
        """Process subscription cancellation."""
        await self._record_subscription_event(
            subscription_id=subscription['id'],
            customer_id=subscription['customer'],
            event_type='subscription_cancelled',
            metadata={
                'status': subscription['status'],
                'cancellation_reason': subscription.get('cancellation_details', {}).get('reason')
            }
        )

    async def _record_subscription_event(
        self,
        subscription_id: str,
        customer_id: str,
        event_type: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Record subscription events in the database."""
        try:
            # Convert metadata to JSON string
            metadata_json = json.dumps(metadata)

            # Record event
            await query_db(f"""
                INSERT INTO subscription_events (
                    subscription_id,
                    customer_id,
                    event_type,
                    metadata,
                    recorded_at
                ) VALUES (
                    '{subscription_id}',
                    '{customer_id}',
                    '{event_type}',
                    '{metadata_json}'::jsonb,
                    NOW()
                )
            """)
        except Exception as e:
            logger.error(f"Failed to record subscription event: {str(e)}")
