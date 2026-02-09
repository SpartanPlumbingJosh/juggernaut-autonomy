"""Stripe payment processing integration with retries and exponential backoff."""
import os
import stripe
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

from payment_processors.base_processor import BasePaymentProcessor

class StripeProcessor(BasePaymentProcessor):
    def __init__(self):
        self.api_key = os.getenv('STRIPE_API_KEY')
        stripe.api_key = self.api_key
        self.max_retries = 3
        self.timeout = 30
        
    async def create_customer(self, email: str, metadata: Dict[str, str] = None) -> Tuple[Optional[str], Optional[str]]:
        """Create a Stripe customer with retry logic."""
        for attempt in range(self.max_retries):
            try:
                customer = stripe.Customer.create(
                    email=email,
                    metadata=metadata or {},
                    api_key=self.api_key
                )
                return customer.id, None
            except stripe.error.StripeError as e:
                if attempt == self.max_retries - 1:
                    return None, str(e)
                time.sleep(2 ** attempt)  # Exponential backoff

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Dict[str, str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """Create subscription with retry logic."""
        for attempt in range(self.max_retries):
            try:
                subscription = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{"price": price_id}],
                    metadata=metadata or {},
                    api_key=self.api_key
                )
                return subscription.id, None
            except stripe.error.StripeError as e:
                if attempt == self.max_retries - 1:
                    return None, str(e)
                time.sleep(2 ** attempt)

    async def record_payment_event(
        self,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record Stripe payment event in our revenue tracking system."""
        event_type = event_data.get('type')
        amount = event_data.get('amount', 0)
        currency = event_data.get('currency', 'usd')
        
        # Skip events we don't care about
        if event_type not in ['payment_intent.succeeded', 'charge.succeeded']:
            return
        
        # Record as revenue event
        return {
            'event_type': 'revenue',
            'amount_cents': amount,
            'currency': currency,
            'source': 'stripe',
            'recorded_at': datetime.utcnow().isoformat(),
            'metadata': {
                'stripe_event_id': event_data.get('id'),
                'stripe_event_type': event_type
            }
        }
