"""
Stripe payment provider implementation.
"""
import stripe
from typing import Dict, Any, Optional
import json
from datetime import datetime, timezone
from ..config import STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET

stripe.api_key = STRIPE_API_KEY

class Provider:
    """Stripe payment provider."""
    
    def __init__(self):
        """Initialize Stripe client."""
        stripe.api_key = STRIPE_API_KEY

    async def create_charge(self, amount: float, currency: str,
                          metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create Stripe charge."""
        try:
            charge = stripe.Charge.create(
                amount=int(amount * 100),
                currency=currency.lower(),
                description=metadata.get('description', ''),
                metadata=metadata,
                source=metadata.get('payment_method'),
                capture=True
            )
            return json.loads(str(charge))
        except stripe.error.StripeError as e:
            raise ValueError(f"Stripe charge failed: {str(e)}")

    async def create_subscription(self, plan_id: str, customer_data: Dict[str, Any],
                                metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create Stripe subscription."""
        try:
            customer = stripe.Customer.create(
                email=customer_data['email'],
                name=customer_data.get('name', ''),
                metadata=metadata
            )
            
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{'price': plan_id}],
                metadata=metadata
            )
            
            return {
                'customer_id': customer.id,
                'subscription_id': subscription.id,
                'status': subscription.status
            }
        except stripe.error.StripeError as e:
            raise ValueError(f"Stripe subscription failed: {str(e)}")

    async def verify_webhook(self, payload: Dict[str, Any],
                           signature: Optional[str] = None) -> bool:
        """Verify Stripe webhook signature."""
        if not signature:
            return False
            
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                STRIPE_WEBHOOK_SECRET
            )
            return True
        except ValueError:
            return False
        except stripe.error.SignatureVerificationError:
            return False
