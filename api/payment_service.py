import os
import stripe
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from core.database import query_db

# Initialize Stripe with API key from environment
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

class PaymentService:
    """Handles Stripe payment processing and webhook events."""
    
    @staticmethod
    async def create_payment_intent(amount_cents: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe PaymentIntent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata,
                payment_method_types=['card'],
                capture_method='automatic'
            )
            return {
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'status': intent.status
            }
        except stripe.error.StripeError as e:
            return {'error': str(e)}

    @staticmethod
    async def handle_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
        except ValueError as e:
            return {'error': 'Invalid payload', 'status_code': 400}
        except stripe.error.SignatureVerificationError as e:
            return {'error': 'Invalid signature', 'status_code': 400}

        # Handle specific event types
        if event['type'] == 'payment_intent.succeeded':
            return await PaymentService._handle_payment_success(event['data']['object'])
        elif event['type'] == 'payment_intent.payment_failed':
            return await PaymentService._handle_payment_failure(event['data']['object'])
        
        return {'status': 'unhandled_event_type'}

    @staticmethod
    async def _handle_payment_success(payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Record successful payment in revenue_events."""
        amount_cents = payment_intent['amount']
        metadata = payment_intent.get('metadata', {})
        
        # Check for duplicate processing
        existing = await query_db(
            f"SELECT id FROM revenue_events WHERE metadata->>'payment_intent_id' = '{payment_intent['id']}'"
        )
        if existing.get('rows'):
            return {'status': 'already_processed'}

        # Record revenue event
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                '{payment_intent['currency']}',
                'stripe',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
        """)
        
        return {'status': 'success'}

    @staticmethod
    async def _handle_payment_failure(payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment attempts."""
        error = payment_intent.get('last_payment_error', {}).get('message', 'unknown')
        metadata = payment_intent.get('metadata', {})
        
        # Log failure for recovery
        await query_db(f"""
            INSERT INTO payment_failures (
                id, payment_intent_id, amount_cents, currency,
                error_message, metadata, created_at
            ) VALUES (
                gen_random_uuid(),
                '{payment_intent['id']}',
                {payment_intent['amount']},
                '{payment_intent['currency']}',
                '{error.replace("'", "''")}',
                '{json.dumps(metadata)}'::jsonb,
                NOW()
            )
        """)
        
        return {'status': 'failure_logged'}
