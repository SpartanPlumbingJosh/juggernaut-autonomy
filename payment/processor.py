import os
import stripe
import json
import logging
from datetime import datetime
from typing import Dict, Optional, List

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

class PaymentProcessor:
    """Handle payment processing and webhook events."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.retry_attempts = 3
        
    async def create_checkout_session(self, product_id: str, customer_email: str, 
                                    success_url: str, cancel_url: str) -> Dict:
        """Create Stripe checkout session."""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': product_id,
                    'quantity': 1,
                }],
                mode='payment',
                customer_email=customer_email,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={'created_at': datetime.utcnow().isoformat()}
            )
            return {'success': True, 'session_id': session.id, 'url': session.url}
        except stripe.error.StripeError as e:
            self.logger.error(f"Stripe error creating checkout: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError as e:
            self.logger.error(f"Invalid payload: {str(e)}")
            return {'success': False, 'error': 'Invalid payload'}
        except stripe.error.SignatureVerificationError as e:
            self.logger.error(f"Invalid signature: {str(e)}")
            return {'success': False, 'error': 'Invalid signature'}
        
        # Handle specific event types
        if event['type'] == 'checkout.session.completed':
            return await self._handle_payment_success(event['data']['object'])
        elif event['type'] == 'charge.failed':
            return await self._handle_payment_failure(event['data']['object'])
        
        return {'success': True, 'processed': False}
    
    async def _handle_payment_success(self, session: Dict) -> Dict:
        """Process successful payment."""
        try:
            # Get payment details
            payment_intent = stripe.PaymentIntent.retrieve(session['payment_intent'])
            
            # Record successful payment
            await self._record_transaction(
                amount=payment_intent['amount'],
                currency=payment_intent['currency'],
                payment_id=payment_intent['id'],
                customer_email=session.get('customer_email'),
                metadata=session.get('metadata', {})
            )
            
            # Trigger fulfillment
            await self._fulfill_order(session)
            
            return {'success': True, 'processed': True}
        except Exception as e:
            self.logger.error(f"Error processing payment success: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _handle_payment_failure(self, charge: Dict) -> Dict:
        """Handle failed payment with retry logic."""
        attempt = 0
        while attempt < self.retry_attempts:
            try:
                # Attempt to retry payment
                payment_intent = stripe.PaymentIntent.retrieve(charge['payment_intent'])
                if payment_intent['status'] == 'requires_payment_method':
                    await stripe.PaymentIntent.confirm(
                        payment_intent['id'],
                        payment_method=payment_intent['last_payment_error']['payment_method']['id']
                    )
                    return {'success': True, 'retried': True}
            except Exception as e:
                attempt += 1
                self.logger.warning(f"Payment retry attempt {attempt} failed: {str(e)}")
        
        # If all retries fail, notify customer
        await self._notify_payment_failure(charge)
        return {'success': False, 'error': 'Payment failed after retries'}
    
    async def _record_transaction(self, amount: int, currency: str, 
                                payment_id: str, customer_email: str, 
                                metadata: Dict) -> None:
        """Record transaction in database."""
        # Implement database recording logic
        pass
    
    async def _fulfill_order(self, session: Dict) -> None:
        """Trigger order fulfillment process."""
        # Implement fulfillment logic
        pass
    
    async def _notify_payment_failure(self, charge: Dict) -> None:
        """Notify customer of payment failure."""
        # Implement notification logic
        pass
