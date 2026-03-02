"""
Payment Gateway Integration - Handles payment processing and subscriptions.
"""
import os
import stripe
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

class PaymentGateway:
    """Handles payment processing and subscription management."""
    
    @staticmethod
    def create_customer(email: str, name: str) -> Optional[str]:
        """Create a new customer in Stripe."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={'created_at': datetime.now(timezone.utc).isoformat()}
            )
            return customer.id
        except Exception as e:
            print(f"Error creating customer: {str(e)}")
            return None

    @staticmethod
    def create_payment_intent(amount: int, currency: str, customer_id: str, 
                            metadata: Dict[str, str]) -> Optional[str]:
        """Create a payment intent for immediate payment."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                metadata=metadata,
                payment_method_types=['card'],
                receipt_email=metadata.get('email')
            )
            return intent.client_secret
        except Exception as e:
            print(f"Error creating payment intent: {str(e)}")
            return None

    @staticmethod
    def create_subscription(customer_id: str, price_id: str) -> Optional[str]:
        """Create a recurring subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                expand=['latest_invoice.payment_intent']
            )
            return subscription.id
        except Exception as e:
            print(f"Error creating subscription: {str(e)}")
            return None

    @staticmethod
    def handle_webhook(payload: str, sig_header: str) -> Tuple[bool, Optional[Dict]]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
            
            # Handle specific event types
            if event['type'] == 'payment_intent.succeeded':
                return True, event['data']['object']
            elif event['type'] == 'invoice.payment_succeeded':
                return True, event['data']['object']
            elif event['type'] == 'customer.subscription.deleted':
                return True, event['data']['object']
                
            return False, None
        except Exception as e:
            print(f"Webhook error: {str(e)}")
            return False, None

    @staticmethod
    def get_customer_payment_methods(customer_id: str) -> Optional[Dict]:
        """Retrieve customer's payment methods."""
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type="card"
            )
            return payment_methods.data
        except Exception as e:
            print(f"Error getting payment methods: {str(e)}")
            return None
