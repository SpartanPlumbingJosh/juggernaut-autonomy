"""
Payment Processor - Handles Stripe/PayPal integrations and webhook processing.
"""

import os
import stripe
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Any

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self):
        self.retry_count = 3
        self.retry_delay = 2  # seconds

    async def create_payment_intent(self, amount: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a payment intent with Stripe.
        """
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata,
                payment_method_types=['card'],
            )
            return {
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'status': intent.status
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {str(e)}")
            raise

    async def handle_webhook(self, payload: str, sig_header: str) -> Dict[str, Any]:
        """
        Process Stripe webhook events.
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(f"Invalid payload: {str(e)}")
            return {'status': 'error', 'message': 'Invalid payload'}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {str(e)}")
            return {'status': 'error', 'message': 'Invalid signature'}

        # Handle the event
        event_type = event['type']
        data = event['data']['object']
        
        if event_type == 'payment_intent.succeeded':
            await self._handle_payment_success(data)
        elif event_type == 'payment_intent.payment_failed':
            await self._handle_payment_failure(data)
        elif event_type == 'charge.refunded':
            await self._handle_refund(data)
        
        return {'status': 'success', 'event': event_type}

    async def _handle_payment_success(self, data: Dict[str, Any]) -> None:
        """
        Handle successful payment.
        """
        metadata = data.get('metadata', {})
        amount = data['amount']
        currency = data['currency']
        
        # Record transaction
        await self._record_transaction(
            amount=amount,
            currency=currency,
            status='success',
            payment_intent_id=data['id'],
            metadata=metadata
        )
        
        # Trigger product delivery
        await self._deliver_product(metadata)

    async def _handle_payment_failure(self, data: Dict[str, Any]) -> None:
        """
        Handle failed payment.
        """
        await self._record_transaction(
            amount=data['amount'],
            currency=data['currency'],
            status='failed',
            payment_intent_id=data['id'],
            metadata=data.get('metadata', {})
        )

    async def _handle_refund(self, data: Dict[str, Any]) -> None:
        """
        Handle refunds.
        """
        await self._record_transaction(
            amount=-data['amount_refunded'],
            currency=data['currency'],
            status='refunded',
            payment_intent_id=data['payment_intent'],
            metadata=data.get('metadata', {})
        )

    async def _record_transaction(self, amount: int, currency: str, status: str, 
                               payment_intent_id: str, metadata: Dict[str, Any]) -> None:
        """
        Record transaction in the database.
        """
        try:
            # Insert into revenue_events table
            await query_db(f"""
                INSERT INTO revenue_events (
                    event_type, amount_cents, currency, source,
                    metadata, recorded_at, created_at
                ) VALUES (
                    'payment', {amount}, '{currency}', 'stripe',
                    '{json.dumps(metadata)}', NOW(), NOW()
                )
            """)
        except Exception as e:
            logger.error(f"Failed to record transaction: {str(e)}")
            raise

    async def _deliver_product(self, metadata: Dict[str, Any]) -> None:
        """
        Trigger product delivery based on metadata.
        """
        try:
            product_id = metadata.get('product_id')
            user_id = metadata.get('user_id')
            
            if not product_id or not user_id:
                logger.warning("Missing product_id or user_id in metadata")
                return
            
            # Implement product delivery logic here
            logger.info(f"Delivering product {product_id} to user {user_id}")
            
        except Exception as e:
            logger.error(f"Product delivery failed: {str(e)}")
            raise

    async def generate_invoice(self, payment_intent_id: str) -> Optional[str]:
        """
        Generate and send an invoice for a payment.
        """
        try:
            invoice = stripe.Invoice.create(
                payment_intent=payment_intent_id,
                auto_advance=True
            )
            return invoice.invoice_pdf
        except stripe.error.StripeError as e:
            logger.error(f"Failed to generate invoice: {str(e)}")
            return None
