"""
Payment processing service integrating Stripe and PayPal.
Handles billing, invoicing and receipt generation.
"""
import os
import uuid
import stripe
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import logging

from core.database import query_db

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_API_KEY')
logger = logging.getLogger(__name__)

class PaymentService:
    @staticmethod
    async def create_payment_intent(amount_cents: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create Stripe PaymentIntent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata,
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            return {'success': True, 'client_secret': intent.client_secret}
        except Exception as e:
            logger.error(f"Payment intent creation failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def record_transaction(
        amount_cents: int,
        currency: str,
        source: str,
        event_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Record a revenue transaction in the database."""
        try:
            transaction_id = str(uuid.uuid4())
            recorded_at = datetime.now(timezone.utc).isoformat()
            
            result = await query_db(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at
                ) VALUES (
                    '{transaction_id}', '{event_type}', {amount_cents}, 
                    '{currency}', '{source}', $${metadata or {}}$$, 
                    '{recorded_at}'
                )
                RETURNING id
                """
            )
            
            if not result.get('rows'):
                raise Exception("Failed to insert transaction")
            
            return {'success': True, 'transaction_id': transaction_id}
        except Exception as e:
            logger.error(f"Transaction recording failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def generate_invoice(payment_intent_id: str) -> Optional[str]:
        """Generate invoice PDF from Stripe payment."""
        try:
            invoice = stripe.Invoice.create_from_payment_intent(
                payment_intent_id,
            )
            invoice_file = stripe.Invoice.pdf(invoice.id)
            return invoice_file.url
        except Exception as e:
            logger.error(f"Invoice generation failed: {str(e)}")
            return None
