"""
Stripe Payment Processor - Handles all payment processing workflows including:
- Checkout session creation
- Webhook handling
- Subscription management
- Digital fulfillment
"""
import os
import logging
import stripe
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import Request, HTTPException

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
endpoint_secret = os.getenv('STRIPE_ENDPOINT_SECRET')
webhook_url = os.getenv('STRIPE_WEBHOOK_URL')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PaymentProcessor:
    @staticmethod
    async def create_checkout_session(
        product_id: str,
        quantity: int = 1,
        customer_email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create Stripe checkout session for one-time payment"""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': product_id,
                    'quantity': quantity,
                }],
                mode='payment',
                success_url=f"{webhook_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{webhook_url}/cancel",
                customer_email=customer_email,
                metadata=metadata or {},
                expires_at=int((datetime.now() + timedelta(hours=24)).timestamp())
            )
            return {
                'success': True,
                'session_id': session.id,
                'url': session.url
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    async def create_subscription(
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create recurring subscription"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                metadata=metadata or {},
                expand=['latest_invoice.payment_intent']
            )
            return {
                'success': True,
                'subscription_id': subscription.id,
                'status': subscription.status
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating subscription: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    async def handle_webhook(request: Request) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError as e:
            logger.error(f"Invalid payload: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Handle various event types
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            return await PaymentProcessor._handle_successful_payment(session)
        elif event['type'] == 'invoice.paid':
            invoice = event['data']['object']
            return await PaymentProcessor._handle_subscription_payment(invoice)
        elif event['type'] == 'invoice.payment_failed':
            invoice = event['data']['object']
            return await PaymentProcessor._handle_payment_failure(invoice)

        return {'success': True}

    @staticmethod
    async def _handle_successful_payment(session: Dict[str, Any]) -> Dict[str, Any]:
        """Fulfill order after successful payment"""
        logger.info(f"Processing successful payment for session: {session['id']}")
        
        # Retrieve customer details
        customer = stripe.Customer.retrieve(session['customer'])
        
        # Generate and send receipt
        receipt = await PaymentProcessor._generate_receipt(
            amount=session['amount_total']/100,
            currency=session['currency'],
            customer_name=customer.name,
            email=customer.email
        )
        
        # Fulfill product/service
        await PaymentProcessor._fulfill_order(
            customer_id=session['customer'],
            product_id=session['line_items']['data'][0]['price']['id'],
            metadata=session.get('metadata', {})
        )
        
        return {'success': True}

    @staticmethod
    async def _handle_subscription_payment(invoice: Dict[str, Any]) -> Dict[str, Any]:
        """Handle recurring subscription payment"""
        logger.info(f"Processing subscription payment: {invoice['id']}")
        
        customer = stripe.Customer.retrieve(invoice['customer'])
        subscription = stripe.Subscription.retrieve(invoice['subscription'])
        
        # Generate receipt
        receipt = await PaymentProcessor._generate_receipt(
            amount=invoice['amount_paid']/100,
            currency=invoice['currency'],
            customer_name=customer.name,
            email=customer.email,
            is_subscription=True
        )
        
        # Continue service access
        await PaymentProcessor._update_subscription_access(
            subscription_id=subscription.id,
            customer_id=customer.id
        )
        
        return {'success': True}

    @staticmethod
    async def _handle_payment_failure(invoice: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment attempt"""
        logger.warning(f"Payment failed for invoice: {invoice['id']}")
        
        customer = stripe.Customer.retrieve(invoice['customer'])
        subscription = stripe.Subscription.retrieve(invoice['subscription'])
        
        # Notify customer
        await PaymentProcessor._send_payment_failure_notification(
            customer_email=customer.email,
            amount=invoice['amount_due']/100,
            currency=invoice['currency']
        )
        
        return {'success': True}

    @staticmethod
    async def _generate_receipt(
        amount: float,
        currency: str,
        customer_name: str,
        email: str,
        is_subscription: bool = False
    ) -> Dict[str, Any]:
        """Generate and send payment receipt"""
        # Implement receipt generation logic
        # This could send an email via SendGrid, Mailchimp, etc.
        # Or store receipt in database for user dashboard
        pass

    @staticmethod
    async def _fulfill_order(
        customer_id: str,
        product_id: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fulfill digital product/service"""
        # Implement fulfillment logic:
        # - Generate license keys
        # - Grant API access
        # - Add to user account
        # - Trigger digital delivery
        pass

    @staticmethod
    async def _update_subscription_access(
        subscription_id: str,
        customer_id: str
    ) -> Dict[str, Any]:
        """Update subscription access in system"""
        # Update user account status
        # Extend access period
        pass

    @staticmethod
    async def _send_payment_failure_notification(
        customer_email: str,
        amount: float,
        currency: str
    ) -> Dict[str, Any]:
        """Notify customer of payment failure"""
        # Send email/SMS notification
        pass
