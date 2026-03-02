import os
import stripe
from typing import Dict, Any, Optional
from datetime import datetime
from core.database import query_db

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

class PaymentService:
    async def create_checkout_session(
        self, 
        price_id: str, 
        customer_email: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create Stripe checkout session."""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='payment',
                customer_email=customer_email,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata or {}
            )
            
            # Record payment intent
            await self._record_payment_event(
                session_id=session.id,
                customer_email=customer_email,
                amount=session.amount_total,
                currency=session.currency,
                status='created'
            )
            
            return {'success': True, 'checkout_url': session.url}
            
        except stripe.error.StripeError as e:
            return {'success': False, 'error': str(e)}

    async def handle_webhook(self, payload: str, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
            
            event_type = event['type']
            session = event['data']['object']
            
            if event_type == 'checkout.session.completed':
                await self._record_payment_event(
                    session_id=session['id'],
                    customer_email=session['customer_email'],
                    amount=session['amount_total'],
                    currency=session['currency'],
                    status='completed',
                    payment_intent=session['payment_intent']
                )
                
                # Trigger delivery
                await self._trigger_delivery(
                    session_id=session['id'],
                    customer_email=session['customer_email'],
                    metadata=session.get('metadata', {})
                )
            
            return {'success': True}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _record_payment_event(
        self,
        session_id: str,
        customer_email: str,
        amount: int,
        currency: str,
        status: str,
        payment_intent: Optional[str] = None
    ) -> None:
        """Record payment event in database."""
        query = """
        INSERT INTO payment_events (
            session_id, customer_email, amount_cents, currency,
            status, payment_intent, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        await query_db(query, [
            session_id, customer_email, amount, currency,
            status, payment_intent
        ])

    async def _trigger_delivery(
        self,
        session_id: str,
        customer_email: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Trigger product/service delivery."""
        # TODO: Implement delivery logic
        pass
