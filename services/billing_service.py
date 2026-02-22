import os
import stripe
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

logger = logging.getLogger(__name__)

class BillingService:
    """Handles all billing operations with Stripe."""
    
    @staticmethod
    def create_customer(email: str, name: str) -> Tuple[Optional[str], Optional[str]]:
        """Create a new Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={'onboarded_at': datetime.utcnow().isoformat()}
            )
            return customer.id, None
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return None, str(e)

    @staticmethod
    def create_subscription(
        customer_id: str, 
        price_id: str,
        metadata: Optional[Dict] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """Create a subscription for a customer."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent'],
                metadata=metadata or {}
            )
            return subscription.id, None
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return None, str(e)

    @staticmethod
    def handle_webhook(payload: bytes, sig_header: str) -> Tuple[bool, Optional[Dict]]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
            
            if event['type'] == 'payment_intent.succeeded':
                return True, BillingService._handle_payment_success(event)
            elif event['type'] == 'invoice.payment_failed':
                return True, BillingService._handle_payment_failure(event)
            elif event['type'] == 'customer.subscription.deleted':
                return True, BillingService._handle_subscription_canceled(event)
            
            return True, None
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {str(e)}")
            return False, None
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {str(e)}")
            return False, None
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return False, None

    @staticmethod
    def _handle_payment_success(event: Dict) -> Dict:
        """Handle successful payment event."""
        payment_intent = event['data']['object']
        return {
            'event_type': 'payment_success',
            'customer_id': payment_intent['customer'],
            'amount': payment_intent['amount'],
            'metadata': payment_intent.get('metadata', {})
        }

    @staticmethod
    def _handle_payment_failure(event: Dict) -> Dict:
        """Handle failed payment event."""
        invoice = event['data']['object']
        return {
            'event_type': 'payment_failed',
            'customer_id': invoice['customer'],
            'attempts_remaining': invoice['attempt_count'],
            'next_attempt': invoice['next_payment_attempt']
        }

    @staticmethod
    def _handle_subscription_canceled(event: Dict) -> Dict:
        """Handle subscription cancellation."""
        subscription = event['data']['object']
        return {
            'event_type': 'subscription_canceled',
            'customer_id': subscription['customer'],
            'canceled_at': subscription['canceled_at']
        }
