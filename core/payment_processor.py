import stripe
from typing import Dict, Optional
from config import settings

class PaymentProcessor:
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
    
    def create_checkout_session(
        self, 
        price_id: str, 
        customer_email: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create a Stripe checkout session"""
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{settings.FRONTEND_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/cancel",
            customer_email=customer_email,
            metadata=metadata or {},
        )
        return {
            'session_id': session.id,
            'url': session.url
        }

    def handle_webhook(self, payload: str, sig_header: str) -> Dict:
        """Handle Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            raise ValueError("Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            raise ValueError("Invalid signature")

        # Handle payment success
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            metadata = session.get('metadata', {})
            return self.process_payment_success(
                session_id=session.id,
                customer_email=session.get('customer_email'),
                amount=session.get('amount_total', 0),
                currency=session.get('currency'),
                metadata=metadata
            )

    def process_payment_success(
        self,
        session_id: str,
        customer_email: str,
        amount: int,
        currency: str,
        metadata: Dict
    ) -> Dict:
        """Process a successful payment"""
        return {
            'success': True,
            'session_id': session_id,
            'customer_email': customer_email,
            'amount': amount,
            'currency': currency,
            'metadata': metadata
        }
