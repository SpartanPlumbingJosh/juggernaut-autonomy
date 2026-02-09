import os
import stripe
import logging
from typing import Dict, Optional
from datetime import datetime

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
logger = logging.getLogger(__name__)

class PaymentGateway:
    """Handle payment processing and webhook events."""
    
    def __init__(self):
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    async def create_payment_intent(self, amount: int, currency: str = 'usd', metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent for a given amount."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            return {
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'status': intent.status
            }
        except stripe.error.StripeError as e:
            logger.error(f"Payment intent creation failed: {str(e)}")
            raise
    
    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict:
        """Process Stripe webhook events."""
        event = None
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
        except ValueError as e:
            logger.error(f"Invalid payload: {str(e)}")
            return {'error': 'Invalid payload', 'status': 400}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {str(e)}")
            return {'error': 'Invalid signature', 'status': 400}
        
        # Handle the event
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            await self._handle_successful_payment(payment_intent)
        elif event['type'] == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            await self._handle_failed_payment(payment_intent)
        else:
            logger.info(f"Unhandled event type: {event['type']}")
        
        return {'success': True}
    
    async def _handle_successful_payment(self, payment_intent: Dict) -> None:
        """Process successful payment and trigger service delivery."""
        try:
            # Record revenue event
            await self._record_revenue_event(
                amount=payment_intent['amount'],
                currency=payment_intent['currency'],
                payment_intent_id=payment_intent['id'],
                metadata=payment_intent.get('metadata', {})
            )
            
            # Trigger service delivery
            await self._deliver_service(payment_intent)
            
            logger.info(f"Payment succeeded: {payment_intent['id']}")
        except Exception as e:
            logger.error(f"Failed to process successful payment: {str(e)}")
    
    async def _handle_failed_payment(self, payment_intent: Dict) -> None:
        """Handle failed payment attempts."""
        logger.warning(f"Payment failed: {payment_intent['id']}")
        # TODO: Implement retry logic or notify user
    
    async def _record_revenue_event(self, amount: int, currency: str, payment_intent_id: str, metadata: Dict) -> None:
        """Record revenue event in database."""
        # Convert amount from cents to dollars
        amount_dollars = amount / 100
        
        # Record event
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount},
                '{currency}',
                'stripe',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
        """)
    
    async def _deliver_service(self, payment_intent: Dict) -> None:
        """Automatically deliver purchased service."""
        # Extract service details from metadata
        service_type = payment_intent['metadata'].get('service_type')
        
        # TODO: Implement service delivery logic based on service type
        logger.info(f"Delivering service: {service_type}")
        
        # Mark service as delivered
        await query_db(f"""
            UPDATE revenue_events
            SET metadata = metadata || '{"delivered": true}'::jsonb
            WHERE metadata->>'payment_intent_id' = '{payment_intent['id']}'
        """)
