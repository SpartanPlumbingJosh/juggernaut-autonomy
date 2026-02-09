"""
Payment Processor - Handles payment gateway integration, subscriptions, and billing.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import stripe  # Assuming Stripe as primary payment gateway
from core.database import query_db

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.gateway = stripe

    async def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a new customer in payment gateway."""
        try:
            customer = self.gateway.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_subscription(self, customer_id: str, price_id: str, trial_days: int = 0) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            subscription = self.gateway.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                trial_period_days=trial_days
            )
            return {"success": True, "subscription_id": subscription.id}
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """Process payment gateway webhook events."""
        try:
            event = self.gateway.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )

            if event['type'] == 'payment_intent.succeeded':
                return await self._handle_successful_payment(event['data']['object'])
            elif event['type'] == 'invoice.payment_succeeded':
                return await self._handle_recurring_payment(event['data']['object'])
            elif event['type'] == 'payment_intent.payment_failed':
                return await self._handle_failed_payment(event['data']['object'])

            return {"success": True, "handled": False}
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _handle_successful_payment(self, payment_intent: Dict) -> Dict[str, Any]:
        """Record successful one-time payment."""
        amount = payment_intent['amount'] / 100  # Convert cents to dollars
        currency = payment_intent['currency']
        customer_id = payment_intent['customer']
        metadata = payment_intent.get('metadata', {})

        await self._record_revenue_event(
            amount_cents=payment_intent['amount'],
            currency=currency,
            event_type='revenue',
            source='payment',
            metadata=metadata,
            customer_id=customer_id
        )

        return {"success": True, "type": "one_time", "amount": amount, "currency": currency}

    async def _handle_recurring_payment(self, invoice: Dict) -> Dict[str, Any]:
        """Record successful recurring payment."""
        amount = invoice['amount_paid'] / 100
        currency = invoice['currency']
        customer_id = invoice['customer']
        subscription_id = invoice['subscription']
        period_start = datetime.fromtimestamp(invoice['period_start'])
        period_end = datetime.fromtimestamp(invoice['period_end'])

        await self._record_revenue_event(
            amount_cents=invoice['amount_paid'],
            currency=currency,
            event_type='revenue',
            source='subscription',
            metadata={
                'subscription_id': subscription_id,
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat()
            },
            customer_id=customer_id
        )

        return {"success": True, "type": "recurring", "amount": amount, "currency": currency}

    async def _handle_failed_payment(self, payment_intent: Dict) -> Dict[str, Any]:
        """Handle failed payment attempt."""
        logger.warning(f"Payment failed: {payment_intent['id']}")
        return {"success": True, "type": "failed", "payment_id": payment_intent['id']}

    async def _record_revenue_event(self, amount_cents: int, currency: str, event_type: str,
                                 source: str, metadata: Dict, customer_id: str) -> None:
        """Record revenue event in database."""
        try:
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, customer_id, recorded_at
                ) VALUES (
                    gen_random_uuid(),
                    '{event_type}',
                    {amount_cents},
                    '{currency}',
                    '{source}',
                    '{json.dumps(metadata)}'::jsonb,
                    '{customer_id}',
                    NOW()
                )
            """)
        except Exception as e:
            logger.error(f"Failed to record revenue event: {str(e)}")

    async def generate_invoice(self, customer_id: str, amount: float, currency: str,
                             description: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Generate and send an invoice."""
        try:
            invoice = self.gateway.Invoice.create(
                customer=customer_id,
                amount=int(amount * 100),  # Convert to cents
                currency=currency,
                description=description,
                metadata=metadata or {},
                auto_advance=True
            )
            return {"success": True, "invoice_id": invoice.id}
        except Exception as e:
            logger.error(f"Failed to generate invoice: {str(e)}")
            return {"success": False, "error": str(e)}

    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel an active subscription."""
        try:
            subscription = self.gateway.Subscription.delete(subscription_id)
            return {"success": True, "subscription_id": subscription.id}
        except Exception as e:
            logger.error(f"Failed to cancel subscription: {str(e)}")
            return {"success": False, "error": str(e)}

__all__ = ["PaymentProcessor"]
