import stripe
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from core.database import query_db

# Initialize Stripe
stripe.api_key = "sk_test_..."  # Should be from environment variables

class PaymentProcessor:
    """Handles payment processing and retries for failed payments."""
    
    MAX_RETRIES = 3
    RETRY_DELAY = 60  # seconds
    
    async def create_payment_intent(self, amount: int, currency: str, customer_id: str, 
                                  metadata: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
        """Create a payment intent with Stripe."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                metadata=metadata or {},
                payment_method_types=['card'],
                capture_method='automatic'
            )
            return True, intent.id
        except stripe.error.StripeError as e:
            logging.error(f"Payment intent creation failed: {str(e)}")
            return False, None

    async def process_payment(self, amount: int, currency: str, customer_email: str, 
                            metadata: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
        """Process payment with retry logic."""
        customer_id = await self._get_or_create_customer(customer_email)
        if not customer_id:
            return False, None
            
        for attempt in range(self.MAX_RETRIES):
            success, payment_id = await self.create_payment_intent(amount, currency, customer_id, metadata)
            if success:
                return True, payment_id
                
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(self.RETRY_DELAY)
                
        return False, None

    async def _get_or_create_customer(self, email: str) -> Optional[str]:
        """Get or create Stripe customer."""
        try:
            # Check if customer exists
            customers = stripe.Customer.list(email=email, limit=1)
            if customers.data:
                return customers.data[0].id
                
            # Create new customer
            customer = stripe.Customer.create(email=email)
            return customer.id
        except stripe.error.StripeError as e:
            logging.error(f"Customer creation failed: {str(e)}")
            return None

    async def record_payment_event(self, payment_id: str, amount: int, currency: str, 
                                 customer_email: str, metadata: Dict) -> bool:
        """Record payment event in revenue tracking system."""
        try:
            await query_db(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source,
                    metadata, recorded_at, created_at
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
                """
            )
            return True
        except Exception as e:
            logging.error(f"Failed to record payment event: {str(e)}")
            return False
