"""
Autonomous payment processing with Stripe/Paddle integration.
Handles subscriptions, one-time payments, and webhooks.
"""
import os
import stripe
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone

class PaymentProcessor:
    def __init__(self):
        self.stripe_api_key = os.getenv("STRIPE_API_KEY")
        stripe.api_key = self.stripe_api_key
        
    async def create_checkout_session(self, 
                                    price_id: str,
                                    customer_email: str,
                                    success_url: str,
                                    cancel_url: str,
                                    metadata: Optional[Dict] = None) -> Dict:
        """Create Stripe checkout session for one-time or subscription payment"""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription' if 'subscription' in price_id else 'payment',
                customer_email=customer_email,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata or {}
            )
            return {
                "success": True,
                "session_id": session.id,
                "payment_url": session.url
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def handle_webhook(self, payload: bytes, sig_header: str, webhook_secret: str) -> Tuple[int, Dict]:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                await self._fulfill_order(session)
                
            elif event['type'] == 'invoice.paid':
                invoice = event['data']['object']
                await self._handle_recurring_payment(invoice)
                
            elif event['type'] == 'invoice.payment_failed':
                invoice = event['data']['object']
                await self._handle_payment_failure(invoice)
                
            return 200, {"received": True}
            
        except ValueError as e:
            return 400, {"error": str(e)}
        except stripe.error.SignatureVerificationError as e:
            return 400, {"error": str(e)}

    async def _fulfill_order(self, session: Dict) -> None:
        """Fulfill order and trigger product delivery"""
        metadata = session.get("metadata", {})
        customer_email = session.get("customer_email", "")
        
        # TODO: Call product delivery service
        print(f"Order fulfilled for {customer_email} with metadata: {metadata}")

    async def _handle_recurring_payment(self, invoice: Dict) -> None:
        """Process successful recurring payment"""
        customer_email = invoice.get("customer_email", "")
        amount = invoice["amount_paid"] / 100  # Convert to dollars
        
        # TODO: Log revenue event and extend access
        print(f"Recurring payment from {customer_email} for ${amount}")

    async def _handle_payment_failure(self, invoice: Dict) -> None:
        """Handle failed payments"""
        customer_email = invoice.get("customer_email", "")
        
        # TODO: Trigger dunning process or access removal
        print(f"Payment failed for {customer_email}")
