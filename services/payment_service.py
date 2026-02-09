import os
import stripe
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class PaymentResult:
    success: bool
    transaction_id: str  
    amount: float
    currency: str
    timestamp: datetime
    metadata: Dict[str, str]

class PaymentService:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.stripe = stripe
    
    async def create_payment_intent(self, 
                                 amount: float,
                                 currency: str = 'usd',
                                 metadata: Optional[Dict] = None) -> PaymentResult:
        """Create a Stripe payment intent."""
        try:
            intent = self.stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Stripe uses cents
                currency=currency,
                metadata=metadata or {}
            )
            return PaymentResult(
                success=True,
                transaction_id=intent.id,
                amount=amount,
                currency=currency,
                timestamp=datetime.utcnow(),
                metadata=metadata or {}
            )
        except Exception as e:
            logger.error(f"Payment failed: {str(e)}")
            raise

    async def record_transaction(self,
                              execute_sql: Callable[[str], Dict],
                              result: PaymentResult) -> bool:
        """Record transaction in revenue_events table."""
        try:
            await execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {int(result.amount * 100)},
                    '{result.currency}',
                    'stripe',
                    '{json.dumps(result.metadata)}',
                    NOW()
                )
            """)
            return True
        except Exception as e:
            logger.error(f"Transaction recording failed: {str(e)}")
            return False
